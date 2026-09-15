"""FastAPI dependency injection functions (Gate 07).

All dependencies are request-scoped. No global mutable singletons carry
request-specific actor/tenant/patient/role data.

Authentication pipeline:

    Authorization: Bearer <token>
        → extract token
        → cryptographic verification (Gate 06 HS256 primitive)
        → trusted claims
        → issuer/expiry validation
        → principal construction
        → AuthenticatedContext

Tenant propagation:

    AuthenticatedContext.tenant_id
        → SqlAlchemyUnitOfWork(session_factory, tenant_id)
        → session-local ``set_config('app.current_tenant_id', :tid, true)``
        → PostgreSQL RLS

The HTTP layer never accepts tenant_id from ordinary JSON as authoritative.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header, HTTPException

from backend.infrastructure.config.clock import SystemClock
from backend.infrastructure.config.database import create_db_engine, create_session_factory
from backend.infrastructure.config.id_generator import Uuid4IdGenerator
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    DefaultAuthorizationPolicy,
)
from backend.interfaces.http.v2.security.jwt import JwtSignatureError, verify_hs256
from backend.interfaces.http.v2.security.roles import role_tokens

if TYPE_CHECKING:
    from sqlalchemy import Engine

logger = logging.getLogger(__name__)

_config_cache: dict = {}
_engine_cache: dict[str, Engine] = {}


def _load_config() -> dict:
    if not _config_cache:
        from config.settings import Settings

        settings = Settings()
        _config_cache["jwt_secret"] = settings.identity.client_secret or "dev-secret-change-in-production"
        _config_cache["issuer_url"] = settings.identity.issuer_url or "http://localhost:8080/realms/thali"
        _config_cache["db_url"] = settings.database.url or "sqlite:///:memory:"
        _config_cache["whatsapp_verify_token"] = settings.whatsapp.verify_token or "thali-dev-verify-token"
        _config_cache["whatsapp_app_secret"] = settings.whatsapp.app_secret or "dev-webhook-secret-change-in-production"
        _config_cache["app_env"] = settings.app.env
    return _config_cache


def reset_config_cache() -> None:
    """Clear cached configuration (used by tests)."""
    _config_cache.clear()


def get_jwt_secret() -> str:
    return _load_config()["jwt_secret"]


def get_issuer_url() -> str:
    return _load_config()["issuer_url"]


def get_db_url() -> str:
    return _load_config()["db_url"]


def get_whatsapp_verify_token() -> str:
    return _load_config()["whatsapp_verify_token"]


def get_whatsapp_app_secret() -> str:
    return _load_config()["whatsapp_app_secret"]


def get_app_env() -> str:
    return _load_config()["app_env"]


def get_authorization_policy() -> DefaultAuthorizationPolicy:
    return DefaultAuthorizationPolicy()


async def get_verified_claims(
    authorization: str | None = Header(None),
) -> dict:
    """Extract and cryptographically verify the JWT from the Authorization header.

    Never authorizes using an unverified token. Rejects expired, malformed,
    invalid-signature, unsupported-algorithm, wrong-issuer, missing-subject and
    missing-tenant tokens.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token is required")

    token = authorization[len("Bearer "):]
    secret = get_jwt_secret()

    try:
        result = verify_hs256(token, secret)
    except JwtSignatureError as exc:
        raise HTTPException(status_code=401, detail="Authentication credentials are invalid") from exc
    except Exception as exc:
        # Any structurally-malformed token (non-dict header, bad segments, etc.)
        # must fail closed as 401, never as a server error.
        raise HTTPException(status_code=401, detail="Authentication credentials are invalid") from exc

    payload = result.payload

    exp = payload.get("exp")
    if exp is not None and time.time() > exp:
        raise HTTPException(status_code=401, detail="Authentication token has expired")

    expected_iss = get_issuer_url()
    if expected_iss:
        iss = payload.get("iss")
        if not iss or iss != expected_iss:
            raise HTTPException(status_code=401, detail="Invalid issuer")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    tenant_id_claim = payload.get("tenant_id")
    if not tenant_id_claim:
        raise HTTPException(status_code=401, detail="Token missing tenant_id claim")
    try:
        UUID(str(tenant_id_claim))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Malformed tenant identifier") from exc

    return payload


async def get_authenticated_context(
    claims: Annotated[dict, Depends(get_verified_claims)],
) -> AuthenticatedContext:
    """Construct AuthenticatedContext from verified JWT claims.

    actor_id, tenant_id, roles, facility_id come from verified claims ONLY,
    never from request bodies.
    """
    try:
        actor_id = UUID(str(claims["sub"]))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Malformed subject claim") from exc

    tenant_id = UUID(str(claims["tenant_id"]))

    raw_roles: list[str] = []
    realm_access = claims.get("realm_access")
    if realm_access is not None:
        if not isinstance(realm_access, dict):
            raise HTTPException(status_code=401, detail="Malformed role claims")
        claimed = realm_access.get("roles", [])
        if not isinstance(claimed, list):
            raise HTTPException(status_code=401, detail="Malformed role claims")
        raw_roles = [r for r in claimed if isinstance(r, str)]

    normalized = role_tokens(raw_roles)

    facility_id: UUID | None = None
    facility_raw = claims.get("facility_id")
    if facility_raw:
        try:
            facility_id = UUID(str(facility_raw))
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=401, detail="Malformed facility identifier") from exc

    username = claims.get("preferred_username", "")

    return AuthenticatedContext(
        actor_id=actor_id,
        tenant_id=tenant_id,
        roles=tuple(normalized),
        facility_id=facility_id,
        username=username,
    )


def _get_engine(db_url: str) -> Engine:
    engine = _engine_cache.get(db_url)
    if engine is None:
        engine = create_db_engine(db_url)
        _engine_cache[db_url] = engine
    return engine


def get_engine() -> Engine:
    """Return the configured application database engine (readiness use)."""
    return _get_engine(get_db_url())


async def get_unit_of_work(
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
) -> AsyncGenerator[SqlAlchemyUnitOfWork, None]:
    """Open a UnitOfWork bound to the authenticated tenant.

    The tenant binding happens BEFORE any repository access. For PostgreSQL the
    UoW executes ``set_config('app.current_tenant_id', :tid, true)`` so RLS
    applies transaction-locally.
    """
    engine = _get_engine(get_db_url())
    session_factory = create_session_factory(engine)
    uow = SqlAlchemyUnitOfWork(session_factory, ctx.tenant_id)
    try:
        yield uow
    finally:
        uow.close()


def get_event_publisher(
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
):
    """Build a domain event publisher bound to the current UoW transaction."""
    from backend.infrastructure.persistence.uow.outbox_publisher import (
        SqlAlchemyOutboxDomainEventPublisher,
    )

    return SqlAlchemyOutboxDomainEventPublisher(uow.session, uow.tenant_id)


def get_clock() -> SystemClock:
    return SystemClock()


def get_id_generator() -> Uuid4IdGenerator:
    return Uuid4IdGenerator()