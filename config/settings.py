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
    url: str = Field(default="", description="SQLAlchemy database URL (unused at Gate 03)")
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)


class RedisConfig(BaseModel):
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
    client_id: str = Field(default="")
    client_secret: str = Field(default="", description="never commit real secrets")


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
    log_level: str = Field(default="INFO")
    structured_logs: bool = Field(default=False)
    metrics_enabled: bool = Field(default=False)
    tracing_enabled: bool = Field(default=False)


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