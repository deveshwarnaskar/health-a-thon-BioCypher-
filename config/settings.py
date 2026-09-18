"""Target system configuration schema (Gate 03).

Pure configuration layer built on pydantic-settings / Pydantic v2. It is NOT
consumed by the legacy Aahaar prototype yet and connects to NO external
service. All credentials default to empty values; nothing sensitive is
embedded in source control.
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
    pool_size: int = Field(default=5, ge=1, description="number of connections to keep open in the pool")
    max_overflow: int = Field(default=10, ge=0, description="maximum overflow connections above pool_size")
    pool_timeout: float = Field(default=5.0, ge=0.5, le=60.0, description="seconds to wait for a connection from the pool")
    pool_recycle: int = Field(default=3600, ge=60, description="seconds after which a connection is recycled")
    pool_pre_ping: bool = Field(default=True, description="test connections for liveness on checkout")


class RedisConfig(BaseModel):
    enabled: bool = Field(
        default=False,
        description="enable distributed rate-limit coordination (default OFF preserves the offline test baseline)",
    )
    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    password: str | None = Field(default=None, description="leave unset; never commit real passwords")
    db: int = Field(default=0, ge=0)


class StorageConfig(BaseModel):
    endpoint_url: str = Field(default="", description="S3-compatible endpoint (S3 integration deferred)")
    bucket: str = Field(default="")
    region: str = Field(default="")
    access_key_id: str = Field(default="")
    secret_access_key: str = Field(default="")


class IdentityConfig(BaseModel):
    issuer_url: str = Field(default="", description="Keycloak/OIDC issuer (integration deferred)")
    realm: str = Field(default="")
    client_id: str = Field(default="", description="backend client/resource identifier; also the expected JWT audience")
    client_secret: str = Field(default="", description="never commit real secrets")
    allowed_algorithms: str = Field(
        default="RS256",
        description="comma-separated allow-list of JWT algorithms accepted at the trust boundary; RS256 (Keycloak JWKS) is the production policy, HS256 is development/testing only",
    )
    jwks_uri: str = Field(
        default="",
        description="explicit JWKS endpoint; when empty, OIDC discovery metadata from the issuer is used",
    )


class WhatsAppConfig(BaseModel):
    verify_token: str = Field(default="", description="Meta webhook verify token (empty default)")
    app_secret: str = Field(default="", description="Meta app secret used to verify X-Hub-Signature-256")
    access_token: str = Field(default="")
    phone_number_id: str = Field(default="")
    api_version: str = Field(default="v21.0")


class AIConfig(BaseModel):
    provider: str = Field(default="gemini")
    model: str = Field(default="")
    api_key: str = Field(default="", description="never commit real API keys")


class ObservabilityConfig(BaseModel):
    log_level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")
    structured_logs: bool = Field(default=False, description="Enable machine-readable JSON structured logs")
    service_name: str = Field(default="thali-plate", description="Service identifier for logs, metrics, and traces")
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus operational metrics collection")
    metrics_path: str = Field(default="/metrics", description="Endpoint path for Prometheus metrics")
    metrics_require_auth: bool = Field(default=False, description="Require token or internal network boundary for /metrics")
    metrics_auth_token: str = Field(default="", description="Bearer / header token for scraping /metrics when auth required")
    tracing_enabled: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    tracing_exporter: str = Field(default="memory", description="Span exporter: memory, console, otlp")
    tracing_otlp_endpoint: str = Field(default="", description="OTLP collector endpoint (e.g. http://collector:4318/v1/traces)")
    tracing_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="Trace sampling probability [0.0, 1.0]")


class SecurityConfig(BaseModel):
    allowed_origins: List[str] = Field(default_factory=list)
    session_ttl_minutes: int = Field(default=60, ge=5)


class Settings(BaseSettings):
    """Environment-driven settings. Overridable via ``THALI_APP__ENV``-style
    variable names or a ``.env`` file. No service is contacted on load."""

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
    identity: IdentityConfig = IdentityConfig()
    whatsapp: WhatsAppConfig = WhatsAppConfig()
    ai: AIConfig = AIConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    security: SecurityConfig = SecurityConfig()


class SecurityConfigurationError(ValueError):
    """Raised when security-critical configuration violates production invariants."""

    pass


INSECURE_SECRETS_BLOCKLIST: frozenset[str] = frozenset(
    {
        "dev-secret-change-in-production",
        "dev-webhook-secret-change-in-production",
        "rehearsal-secret-for-idempotency-only",
        "thali-dev-verify-token",
        "minioadmin",
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

ASYMMETRIC_JWT_ALGORITHMS: frozenset[str] = frozenset(
    {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"}
)
SYMMETRIC_JWT_ALGORITHMS: frozenset[str] = frozenset({"HS256", "HS384", "HS512"})


def validate_security_configuration(settings: Settings) -> None:
    """Validate security and cryptographic invariants.

    In production (``settings.app.env == 'production'``), this enforces fail-closed
    validation on all security boundaries:
    - Rejects default, missing, or short (<32 chars) client secrets
    - Rejects symmetric algorithms (HS256) and requires asymmetric algorithms (RS256)
    - Enforces https:// scheme on Keycloak/OIDC issuer URL
    - Enforces non-empty client_id (JWT audience)
    - Rejects SQLite databases
    - Rejects default webhook secrets if provided
    - Enforces secure Redis credentials when Redis is enabled
    - Enforces non-placeholder Storage credentials if storage is configured
    - Forbids wildcard CORS origins
    """
    env = (settings.app.env or "").strip().lower()
    if env != "production":
        return

    # 1. Identity client_secret
    client_secret = (settings.identity.client_secret or "").strip()
    if not client_secret:
        raise SecurityConfigurationError(
            "Production environment requires identity.client_secret to be set."
        )
    if client_secret.lower() in INSECURE_SECRETS_BLOCKLIST:
        raise SecurityConfigurationError(
            "Production environment rejected insecure/placeholder identity.client_secret."
        )
    if len(client_secret) < 32:
        raise SecurityConfigurationError(
            "Production environment requires identity.client_secret to have at least 32 characters of entropy."
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