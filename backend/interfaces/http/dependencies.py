"""FastAPI dependency injection functions (Gate 07 + Gate 10C-R).

All dependencies are request-scoped. No global mutable singletons carry
request-specific actor/tenant/patient/role data.

Authentication pipeline (production trust boundary):

    Authorization: Bearer <token>
        → extract token
        → algorithm allow-list policy (default RS256; HS256 development-only)
        → RS256: Keycloak JWKS signature verification (kid-selected key)
          HS256: stdlib HMAC verification (explicit dev/test config)
        → issuer/audience/expiry validation (configured values, never token)
        → trusted claims
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
from typing import TYPE_CHECKING, Annotated, Any, AsyncGenerator
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
    RelationshipAuthorizationPolicy,
)
from backend.interfaces.http.v2.security.jwt import (
    JwtSignatureError,
    TokenVerificationError,
    jwt_header,
    verify_hs256,
    verify_rs256,
)
from backend.interfaces.http.v2.security.jwks import JwksClient
from backend.interfaces.http.v2.security.roles import role_tokens

if TYPE_CHECKING:
    from sqlalchemy import Engine

logger = logging.getLogger(__name__)

_config_cache: dict = {}
_engine_cache: dict[str, Engine] = {}
_jwks_client: JwksClient | None = None


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
        # Gate 10C-R trust-boundary policy: explicit allow-list (default RS256).
        # HS256 is development/testing ONLY and is never active without an
        # explicit THALI_IDENTITY__ALLOWED_ALGORITHMS override.
        configured = (settings.identity.allowed_algorithms or "RS256").split(",")
        _config_cache["allowed_algorithms"] = {
            a.strip().upper() for a in configured if a.strip()
        } or {"RS256"}
        _config_cache["jwks_uri"] = (settings.identity.jwks_uri or "").strip()
        # Expected JWT audience == the configured backend client/resource
        # identifier. Empty => audience validation fails closed.
        _config_cache["audience"] = (settings.identity.client_id or "").strip()
    return _config_cache


def reset_config_cache() -> None:
    """Clear cached configuration (used by tests)."""
    global _jwks_client
    _config_cache.clear()
    _jwks_client = None


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


def get_allowed_algorithms() -> set[str]:
    return set(_load_config()["allowed_algorithms"])


def get_jwks_uri() -> str:
    return _load_config()["jwks_uri"]


def get_expected_audience() -> str:
    return _load_config()["audience"]


def _build_jwks_client() -> JwksClient:
    cfg = _load_config()
    return JwksClient(issuer_url=cfg["issuer_url"], jwks_uri=cfg["jwks_uri"])


def _get_jwks_client() -> JwksClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = _build_jwks_client()
    return _jwks_client


def get_authorization_policy() -> RelationshipAuthorizationPolicy:
    """Return the Gate 08 policy: coarse RBAC + relational identity grants."""
    return RelationshipAuthorizationPolicy()


def _audience_matches(aud: Any, expected: str) -> bool:
    return aud == expected or (isinstance(aud, list) and expected in aud)


async def verify_access_token(token: str) -> dict:
    """Verify a bearer token against the configured trust boundary.

    Enforces the configured algorithm allow-list (never the token's own button),
    then dispatches to RS256 (Keycloak JWKS) or HS256 (dev/test-only) signature
    verification, and finally applies issuer/audience/expiry/subject/tenant
    claim validation using configured values only.

    Returns the verified claims dict. Raises ``TokenVerificationError`` with a
    safe, non-sensitive message on any failure.
    """
    cfg = _load_config()
    try:
        header = jwt_header(token)
    except JwtSignatureError as exc:
        raise TokenVerificationError("authentication credentials are invalid") from exc

    alg = header.get("alg")
    allowed = cfg["allowed_algorithms"]
    if not isinstance(alg, str) or alg not in allowed:
        raise TokenVerificationError("unsupported token algorithm")

    if alg == "HS256":
        try:
            result = verify_hs256(token, cfg["jwt_secret"])
        except JwtSignatureError as exc:
            raise TokenVerificationError("authentication credentials are invalid") from exc
        payload = result.payload
    elif alg == "RS256":
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise TokenVerificationError("token is missing a key id")
        try:
            signing_key = await _get_jwks_client().signing_key(kid)
            payload = verify_rs256(
                token,
                signing_key.public_key,
                algorithms=[alg],
                audience=cfg["audience"],
                issuer=cfg["issuer_url"],
            )
        except TokenVerificationError:
            raise
        except (JwtSignatureError, Exception) as exc:
            raise TokenVerificationError("authentication credentials are invalid") from exc
    else:
        raise TokenVerificationError("unsupported token algorithm")

    # Common claims validation — uses configured values ONLY, never claims that
    # the token itself asserts as authoritative (defense in depth for both paths).
    expected_iss = cfg["issuer_url"]
    if expected_iss:
        iss = payload.get("iss")
        if not isinstance(iss, str) or iss != expected_iss:
            raise TokenVerificationError("invalid issuer")

    expected_aud = cfg["audience"]
    if not expected_aud:
        raise TokenVerificationError("audience is not configured")
    if not _audience_matches(payload.get("aud"), expected_aud):
        raise TokenVerificationError("token audience mismatch")

    exp = payload.get("exp")
    if exp is not None:
        if not isinstance(exp, (int, float)) or time.time() > exp:
            raise TokenVerificationError("authentication token has expired")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise TokenVerificationError("token missing subject claim")

    tenant_id_claim = payload.get("tenant_id")
    if not tenant_id_claim:
        raise TokenVerificationError("token missing tenant_id claim")
    try:
        UUID(str(tenant_id_claim))
    except (ValueError, TypeError) as exc:
        raise TokenVerificationError("malformed tenant identifier") from exc

    return payload


async def get_verified_claims(
    authorization: str | None = Header(None),
) -> dict:
    """Extract and cryptographically verify the JWT from the Authorization header.

    Never authorizes using an unverified token. Rejects expired, malformed,
    invalid-signature, unsupported-algorithm, wrong-issuer, wrong-audience,
    missing-subject and missing-tenant tokens.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token is required")

    token = authorization[len("Bearer "):]

    try:
        return await verify_access_token(token)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


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


async def get_ops_session() -> AsyncGenerator["Session", None]:
    """Open a tenant-neutral session for operational stores (Gate 09).

    Used where no authenticated tenant exists yet (e.g. webhook receipt +
    outbox enqueue), scoped only to operational tables.
    """
    from sqlalchemy.orm import Session

    engine = _get_engine(get_db_url())
    session_factory = create_session_factory(engine)
    session: Session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_clock() -> SystemClock:
    return SystemClock()


def get_id_generator() -> Uuid4IdGenerator:
    return Uuid4IdGenerator()