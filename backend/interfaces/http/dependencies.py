"""FastAPI dependency injection functions.

Authentication pipeline (custom RS256 — no Keycloak):

    Authorization: Bearer <token>
        → TokenService.verify_token()  (RS256, our own public key)
        → claims: sub, tenant_id, role, facility_id
        → AuthenticatedContext

Tenant propagation:

    AuthenticatedContext.tenant_id
        → SqlAlchemyUnitOfWork(session_factory, tenant_id)
        → set_config('app.current_tenant_id', :tid, true)
        → PostgreSQL RLS
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any, AsyncGenerator
from uuid import UUID

import jwt as pyjwt

from fastapi import Depends, Header, HTTPException

from backend.infrastructure.auth.token_service import TokenService
from backend.infrastructure.config.clock import SystemClock
from backend.infrastructure.config.database import create_db_engine, create_session_factory
from backend.infrastructure.config.id_generator import Uuid4IdGenerator
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    RelationshipAuthorizationPolicy,
)
from backend.interfaces.http.v2.security.jwt import TokenVerificationError
from backend.interfaces.http.v2.security.roles import role_tokens

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_config_cache: dict = {}
_engine_cache: dict[str, Any] = {}
_session_factory_cache: dict[str, Any] = {}
_token_service: TokenService | None = None
_storage_instance: Any | None = None
_jwks_client: Any | None = None


def _load_config() -> dict:
    if not _config_cache:
        from config.settings import Settings, validate_security_configuration

        settings = Settings()
        validate_security_configuration(settings)

        private_key = (settings.auth.private_key_pem or "").replace("\\n", "\n").strip()
        public_key = (settings.auth.public_key_pem or "").replace("\\n", "\n").strip()

        if not private_key or not public_key:
            if settings.app.env == "production":
                raise RuntimeError(
                    "Production requires THALI_AUTH__PRIVATE_KEY_PEM and "
                    "THALI_AUTH__PUBLIC_KEY_PEM to be set."
                )
            logger.warning(
                "No auth keys configured — generating ephemeral RSA-2048 key pair. "
                "Tokens will NOT survive restarts. Set THALI_AUTH__PRIVATE_KEY_PEM "
                "/ THALI_AUTH__PUBLIC_KEY_PEM for stable keys."
            )
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import rsa

            _key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            private_key = _key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode()
            public_key = _key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()

        _config_cache["auth_private_key"] = private_key
        _config_cache["auth_public_key"] = public_key
        _config_cache["access_token_expire_minutes"] = settings.auth.access_token_expire_minutes
        _config_cache["refresh_token_expire_days"] = settings.auth.refresh_token_expire_days
        _config_cache["jwt_secret"] = settings.identity.client_secret or "test-secret"
        _config_cache["issuer_url"] = settings.identity.issuer_url or ""
        _config_cache["audience"] = settings.identity.client_id or ""
        _config_cache["allowed_algorithms"] = (
            {a.strip() for a in settings.identity.allowed_algorithms.split(",")}
            if settings.identity.allowed_algorithms
            else ({"RS256"} if settings.app.env == "production" else {"RS256", "HS256"})
        )
        _config_cache["jwks_uri"] = settings.identity.jwks_uri or ""
        _config_cache["db_url"] = settings.database.url or "sqlite:///:memory:"
        _config_cache["whatsapp_verify_token"] = (
            settings.whatsapp.verify_token or "thali-dev-verify-token"
        )
        _config_cache["whatsapp_app_secret"] = (
            settings.whatsapp.app_secret or "dev-webhook-secret"
        )
        _config_cache["app_env"] = settings.app.env

    return _config_cache


def reset_config_cache() -> None:
    """Clear cached config — used by tests."""
    global _token_service, _storage_instance, _jwks_client
    _config_cache.clear()
    _engine_cache.clear()
    _session_factory_cache.clear()
    _token_service = None
    _storage_instance = None
    _jwks_client = None


def _audience_matches(aud: Any, expected: str) -> bool:
    return aud == expected or (isinstance(aud, list) and expected in aud)


def _build_jwks_client():
    from backend.interfaces.http.v2.security.jwks import JwksClient
    cfg = _load_config()
    return JwksClient(issuer_url=cfg.get("issuer_url", ""), jwks_uri=cfg.get("jwks_uri", ""))


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = _build_jwks_client()
    return _jwks_client


# ---------------------------------------------------------------------------
# TokenService singleton
# ---------------------------------------------------------------------------

def get_token_service() -> TokenService:
    global _token_service
    if _token_service is None:
        cfg = _load_config()
        priv = cfg.get("auth_private_key")
        pub = cfg.get("auth_public_key")
        if not priv or not pub:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import rsa

            _key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            priv = _key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode()
            pub = _key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()
        _token_service = TokenService(
            private_key_pem=priv,
            public_key_pem=pub,
            access_expire_minutes=cfg.get("access_token_expire_minutes", 60),
            refresh_expire_days=cfg.get("refresh_token_expire_days", 7),
            hs256_secret=cfg.get("jwt_secret", "test-secret"),
        )
    return _token_service


# ---------------------------------------------------------------------------
# Config accessors
# ---------------------------------------------------------------------------

def get_db_url() -> str:
    return _load_config()["db_url"]


def get_whatsapp_verify_token() -> str:
    return _load_config()["whatsapp_verify_token"]


def get_whatsapp_app_secret() -> str:
    return _load_config()["whatsapp_app_secret"]


def get_app_env() -> str:
    return _load_config()["app_env"]


def get_allowed_algorithms() -> set[str]:
    cfg = _load_config()
    allowed = cfg.get("allowed_algorithms")
    if allowed:
        if isinstance(allowed, set):
            return allowed
        if isinstance(allowed, str):
            return {a.strip() for a in allowed.split(",")}
    if cfg.get("app_env") == "production":
        return {"RS256"}
    return {"RS256", "HS256"}


# ---------------------------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------------------------

async def verify_access_token(token: str) -> dict:
    """Verify a bearer token against the configured trust boundary.

    Returns the verified claims dict. Raises TokenVerificationError on failure.
    """
    import time
    cfg = _load_config()
    try:
        header = pyjwt.get_unverified_header(token)
    except Exception as exc:
        raise TokenVerificationError("token is invalid") from exc

    alg = header.get("alg")
    allowed = cfg.get("allowed_algorithms", {"RS256", "HS256"})
    if not isinstance(alg, str) or alg not in allowed:
        raise TokenVerificationError("unsupported token algorithm")

    if cfg.get("app_env") == "production" and (alg == "HS256" or alg.startswith("HS")):
        raise TokenVerificationError(f"unsupported token algorithm in production: {alg}")

    if alg == "HS256":
        from backend.interfaces.http.v2.security.jwt import verify_hs256, JwtSignatureError
        try:
            result = verify_hs256(token, cfg["jwt_secret"])
        except JwtSignatureError as exc:
            raise TokenVerificationError("authentication credentials are invalid") from exc
        payload = result.payload
    elif alg == "RS256":
        if cfg.get("jwks_uri"):
            from backend.interfaces.http.v2.security.jwt import verify_rs256, JwtSignatureError
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
            try:
                payload = get_token_service().verify_token(token)
            except TokenVerificationError:
                raise
            except Exception as exc:
                raise TokenVerificationError("authentication credentials are invalid") from exc
    else:
        raise TokenVerificationError("unsupported token algorithm")

    # Common claims validation
    expected_iss = cfg.get("issuer_url")
    if expected_iss:
        iss = payload.get("iss")
        if iss is not None and iss != expected_iss:
            raise TokenVerificationError("invalid issuer")

    expected_aud = cfg.get("audience")
    if expected_aud:
        aud = payload.get("aud")
        if aud is not None and not _audience_matches(aud, expected_aud):
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
        raise TokenVerificationError("malformed tenant_id claim") from exc

    return payload


async def get_verified_claims(
    authorization: str | None = Header(None),
) -> dict:
    """Extract and verify the JWT from the Authorization header.

    Uses our own RS256 public key — no Keycloak, no JWKS endpoint.
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
    """Build AuthenticatedContext from verified JWT claims only."""
    try:
        actor_id = UUID(str(claims["sub"]))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Malformed subject claim") from exc

    try:
        tenant_id = UUID(str(claims["tenant_id"]))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Malformed tenant_id claim") from exc

    # Our tokens: single "role" string claim.
    # Keycloak-compat fallback: realm_access.roles list.
    raw_roles: list[str] = []
    role_claim = claims.get("role")
    if isinstance(role_claim, str) and role_claim:
        raw_roles = [role_claim]
    else:
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
        except (ValueError, TypeError):
            pass

    return AuthenticatedContext(
        actor_id=actor_id,
        tenant_id=tenant_id,
        roles=tuple(normalized),
        facility_id=facility_id,
        username=claims.get("preferred_username", claims.get("sub", "")),
    )


def get_authorization_policy() -> RelationshipAuthorizationPolicy:
    return RelationshipAuthorizationPolicy()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _get_engine(db_url: str) -> Any:
    engine = _engine_cache.get(db_url)
    if engine is None:
        from config.settings import Settings
        settings = Settings()
        engine = create_db_engine(
            db_url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_timeout=settings.database.pool_timeout,
            pool_recycle=settings.database.pool_recycle,
            pool_pre_ping=settings.database.pool_pre_ping,
            pool_reset_on_return="rollback",
        )
        _engine_cache[db_url] = engine
    return engine


def _get_session_factory(db_url: str) -> Any:
    factory = _session_factory_cache.get(db_url)
    if factory is None:
        factory = create_session_factory(_get_engine(db_url))
        _session_factory_cache[db_url] = factory
    return factory


def get_engine() -> Any:
    return _get_engine(get_db_url())


async def get_unit_of_work(
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
) -> AsyncGenerator[SqlAlchemyUnitOfWork, None]:
    """UnitOfWork scoped to the authenticated tenant (RLS enforced)."""
    session_factory = _get_session_factory(get_db_url())
    uow = SqlAlchemyUnitOfWork(session_factory, ctx.tenant_id)
    try:
        yield uow
    finally:
        uow.close()


async def get_ops_session() -> AsyncGenerator["Session", None]:
    """Tenant-neutral session for operational stores (webhook receipt / outbox)."""
    from sqlalchemy.orm import Session
    session_factory = _get_session_factory(get_db_url())
    session: Session = session_factory()
    try:
        yield session
    finally:
        session.close()


async def get_unscoped_session() -> AsyncGenerator["Session", None]:
    """Session with no RLS tenant set — for login (user lookup before auth)."""
    from sqlalchemy.orm import Session
    session_factory = _get_session_factory(get_db_url())
    session: Session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_event_publisher(
    uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
):
    from backend.infrastructure.persistence.uow.outbox_publisher import (
        SqlAlchemyOutboxDomainEventPublisher,
    )
    return SqlAlchemyOutboxDomainEventPublisher(uow.session, uow.tenant_id)


def get_clock() -> SystemClock:
    return SystemClock()


def get_id_generator() -> Uuid4IdGenerator:
    return Uuid4IdGenerator()


def get_object_storage():
    global _storage_instance
    if _storage_instance is None:
        from config.settings import Settings
        from backend.infrastructure.storage.s3_storage import S3ObjectStorage
        settings = Settings()
        sc = settings.storage
        _storage_instance = S3ObjectStorage(
            bucket=(sc.bucket or "thali-documents"),
            endpoint_url=(sc.endpoint_url or None),
            region=(sc.region or None),
            access_key_id=(sc.access_key_id or None),
            secret_access_key=(sc.secret_access_key or None),
        )
    return _storage_instance
