"""Target system configuration schema.

Pure configuration layer built on pydantic-settings / Pydantic v2.
No service is contacted on load.  All credentials default to empty values;
nothing sensitive is embedded in source control.
"""

from typing import List

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    env: str = Field(default="development", description="application environment")
    name: str = Field(default="THALI-PLATE", description="application name")
    version: str = Field(default="0.1.0", description="application version")


class DatabaseConfig(BaseModel):
    url: str = Field(default="", description="SQLAlchemy database URL")
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)
    pool_timeout: float = Field(default=5.0, ge=0.5, le=60.0)
    pool_recycle: int = Field(default=3600, ge=60)
    pool_pre_ping: bool = Field(default=True)


class RedisConfig(BaseModel):
    enabled: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    password: str | None = Field(default=None)
    db: int = Field(default=0, ge=0)


class StorageConfig(BaseModel):
    endpoint_url: str = Field(default="")
    bucket: str = Field(default="")
    region: str = Field(default="")
    access_key_id: str = Field(default="")
    secret_access_key: str = Field(default="")


class AuthConfig(BaseModel):
    """Custom RS256 JWT auth — replaces Keycloak entirely."""

    private_key_pem: str = Field(
        default="",
        description="RSA-2048 private key PEM for JWT signing (never commit real keys)",
    )
    public_key_pem: str = Field(
        default="",
        description="RSA-2048 public key PEM for JWT verification",
    )
    access_token_expire_minutes: int = Field(default=60, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)


# Kept for any legacy code that reads settings.identity — redirects to AuthConfig.
# Will be removed after all callers are updated.
class IdentityConfig(BaseModel):
    issuer_url: str = Field(default="")
    realm: str = Field(default="")
    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    allowed_algorithms: str = Field(default="RS256")
    jwks_uri: str = Field(default="")


class WhatsAppConfig(BaseModel):
    verify_token: str = Field(default="")
    app_secret: str = Field(default="")
    access_token: str = Field(default="")
    phone_number_id: str = Field(default="")
    api_version: str = Field(default="v21.0")


class AIConfig(BaseModel):
    provider: str = Field(default="deterministic")
    model: str = Field(default="")
    api_key: str = Field(default="")


class ObservabilityConfig(BaseModel):
    log_level: str = Field(default="INFO")
    structured_logs: bool = Field(default=False)
    service_name: str = Field(default="thali-plate")
    metrics_enabled: bool = Field(default=True)
    metrics_path: str = Field(default="/metrics")
    metrics_require_auth: bool = Field(default=False)
    metrics_auth_token: str = Field(default="")
    tracing_enabled: bool = Field(default=False)
    tracing_exporter: str = Field(default="memory")
    tracing_otlp_endpoint: str = Field(default="")
    tracing_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)


class SecurityConfig(BaseModel):
    allowed_origins: List[str] = Field(default_factory=list)
    session_ttl_minutes: int = Field(default=60, ge=5)


class Settings(BaseSettings):
    """Environment-driven settings loaded via THALI_* prefix env vars or .env file."""

    model_config = SettingsConfigDict(
        env_prefix="THALI_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    storage: StorageConfig = StorageConfig()
    auth: AuthConfig = AuthConfig()
    # Kept for backward compatibility — deprecated
    identity: IdentityConfig = IdentityConfig()
    whatsapp: WhatsAppConfig = WhatsAppConfig()
    ai: AIConfig = AIConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    security: SecurityConfig = SecurityConfig()


class SecurityConfigurationError(ValueError):
    """Raised when security-critical configuration violates production invariants."""


INSECURE_SECRETS_BLOCKLIST: frozenset[str] = frozenset(
    {
        "dev-secret-change-in-production",
        "dev-webhook-secret-change-in-production",
        "rehearsal-secret-for-idempotency-only",
        "thali-dev-verify-token",
        "minioadmin",
        "thali_minio_dev",
        "secret",
        "changeme",
        "password",
        "admin",
        "12345678",
        "test",
        "dev",
        "development",
    }
)

SYMMETRIC_JWT_ALGORITHMS: frozenset[str] = frozenset({"HS256", "HS384", "HS512"})
ASYMMETRIC_JWT_ALGORITHMS: frozenset[str] = frozenset(
    {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"}
)


def validate_security_configuration(settings: Settings) -> None:
    """Validate security invariants.

    In development this is a no-op.  In production it enforces fail-closed
    checks on all security boundaries.
    """
    env = (settings.app.env or "").strip().lower()
    if env != "production":
        return

    # 1. Client Secret (minimum length and blocklist check)
    secret = (settings.identity.client_secret or "").strip()
    if not secret:
        raise SecurityConfigurationError(
            "Production environment requires identity.client_secret to be configured."
        )
    if secret.lower() in INSECURE_SECRETS_BLOCKLIST:
        raise SecurityConfigurationError(
            "Production environment rejected insecure/placeholder identity.client_secret."
        )
    if len(secret) < 32:
        raise SecurityConfigurationError(
            "Production environment requires identity.client_secret to have at least 32 characters."
        )

    # 2. JWT Allowed Algorithms
    raw_algs = (settings.identity.allowed_algorithms or "").split(",")
    allowed_algs = {a.strip().upper() for a in raw_algs if a.strip()}
    if not allowed_algs:
        raise SecurityConfigurationError(
            "Production environment requires identity.allowed_algorithms to be specified."
        )
    symmetric_present = allowed_algs & SYMMETRIC_JWT_ALGORITHMS
    if symmetric_present:
        raise SecurityConfigurationError(
            f"Production environment forbids symmetric JWT algorithm(s): {', '.join(sorted(symmetric_present))}; must use asymmetric algorithms like RS256."
        )
    asymmetric_present = allowed_algs & ASYMMETRIC_JWT_ALGORITHMS
    if not asymmetric_present:
        raise SecurityConfigurationError(
            "Production environment requires at least one recognized asymmetric JWT algorithm (e.g. RS256)."
        )

    # 3. Keycloak / OIDC Issuer URL
    issuer_url = (settings.identity.issuer_url or "").strip()
    if not issuer_url:
        raise SecurityConfigurationError(
            "Production environment requires identity.issuer_url to be configured."
        )
    if not issuer_url.startswith("https://"):
        raise SecurityConfigurationError(
            "Production environment requires identity.issuer_url to use HTTPS scheme."
        )

    # 4. Client ID (expected audience)
    client_id = (settings.identity.client_id or "").strip()
    if not client_id:
        raise SecurityConfigurationError(
            "Production environment requires identity.client_id (JWT audience) to be configured."
        )

    # 5. Database URL
    db_url = (settings.database.url or "").strip()
    if not db_url:
        raise SecurityConfigurationError(
            "Production environment requires database.url to be configured."
        )
    if db_url.lower().startswith("sqlite:") or "sqlite" in db_url.lower():
        raise SecurityConfigurationError(
            "Production environment forbids SQLite; a production PostgreSQL database URL is required."
        )

    # 6. WhatsApp webhook secret & verify token (if configured)
    whatsapp_secret = (settings.whatsapp.app_secret or "").strip()
    if whatsapp_secret:
        if whatsapp_secret.lower() in INSECURE_SECRETS_BLOCKLIST:
            raise SecurityConfigurationError(
                "Production environment rejected insecure/placeholder whatsapp.app_secret."
            )
        if len(whatsapp_secret) < 32:
            raise SecurityConfigurationError(
                "Production environment requires whatsapp.app_secret to have at least 32 characters."
            )
    verify_token = (settings.whatsapp.verify_token or "").strip()
    if verify_token:
        if verify_token.lower() in INSECURE_SECRETS_BLOCKLIST:
            raise SecurityConfigurationError(
                "Production environment rejected insecure/placeholder whatsapp.verify_token."
            )

    # 7. Redis security boundaries in production (Gate 10P-G)
    if settings.redis.enabled:
        redis_pass = (settings.redis.password or "").strip()
        if not redis_pass:
            raise SecurityConfigurationError(
                "Production environment requires redis.password when Redis coordination is enabled."
            )
        if redis_pass.lower() in INSECURE_SECRETS_BLOCKLIST:
            raise SecurityConfigurationError(
                "Production environment rejected insecure/placeholder redis.password."
            )
        if len(redis_pass) < 16:
            raise SecurityConfigurationError(
                "Production environment requires redis.password to have at least 16 characters."
            )

    # 8. Storage security boundaries in production (Gate 10P-G)
    if (settings.storage.endpoint_url or "").strip() or (settings.storage.bucket or "").strip():
        secret_key = (settings.storage.secret_access_key or "").strip()
        access_key = (settings.storage.access_key_id or "").strip()
        if access_key.lower() in INSECURE_SECRETS_BLOCKLIST or secret_key.lower() in INSECURE_SECRETS_BLOCKLIST:
            raise SecurityConfigurationError(
                "Production environment rejected insecure/placeholder storage credentials (e.g. minioadmin)."
            )

    # 9. CORS allowed origins security in production (Gate 10P-G)
    if settings.security.allowed_origins:
        for origin in settings.security.allowed_origins:
            origin_clean = origin.strip()
            if origin_clean == "*":
                raise SecurityConfigurationError(
                    "Production environment strictly forbids wildcard '*' in security.allowed_origins."
                )
            if origin_clean.startswith("http://") and not origin_clean.startswith("http://localhost"):
                raise SecurityConfigurationError(
                    f"Production environment requires HTTPS scheme for security.allowed_origins: {origin_clean}"
                )

    # 10. Observability security boundaries (Gate 10P-D §19 & §20)
    if settings.observability.metrics_require_auth:
        metrics_token = (settings.observability.metrics_auth_token or "").strip()
        if not metrics_token:
            raise SecurityConfigurationError(
                "Production environment requires observability.metrics_auth_token when metrics_require_auth is enabled."
            )
        if metrics_token.lower() in INSECURE_SECRETS_BLOCKLIST:
            raise SecurityConfigurationError(
                "Production environment rejected insecure/placeholder observability.metrics_auth_token."
            )
        if len(metrics_token) < 16:
            raise SecurityConfigurationError(
                "Production environment requires observability.metrics_auth_token to have at least 16 characters."
            )

    if settings.observability.tracing_otlp_endpoint:
        otlp = settings.observability.tracing_otlp_endpoint.strip()
        if not (otlp.startswith("http://") or otlp.startswith("https://")):
            raise SecurityConfigurationError(
                "Production environment requires observability.tracing_otlp_endpoint to use http:// or https://."
            )

    # 11. Auth private key if configured
    if settings.auth.private_key_pem:
        pk = settings.auth.private_key_pem.strip()
        if "RSA PRIVATE KEY" not in pk and "PRIVATE KEY" not in pk:
            raise SecurityConfigurationError(
                "Production auth.private_key_pem does not appear to be a valid PEM private key."
            )
