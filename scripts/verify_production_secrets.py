#!/usr/bin/env python3
"""Gate 10P-G — Production Secrets & Configuration Validator.

Validates that mandatory production secrets meet cryptographic entropy and
security boundaries, tests fail-closed startup behavior, and ensures no
development placeholders leak into production configuration.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config.settings import (
    AppConfig,
    DatabaseConfig,
    IdentityConfig,
    ObservabilityConfig,
    RedisConfig,
    SecurityConfig,
    SecurityConfigurationError,
    Settings,
    StorageConfig,
    WhatsAppConfig,
    validate_security_configuration,
)


def make_compliant_production_settings() -> Settings:
    """Construct a fully hardened, compliant production Settings object."""
    return Settings(
        app=AppConfig(
            env="production",
            name="THALI-PLATE-PROD",
            version="0.1.0",
        ),
        identity=IdentityConfig(
            issuer_url="https://auth.plate.thali.health/realms/thali-production",
            client_id="thali-backend-api",
            client_secret="a-secure-production-secret-with-more-than-32-chars-entropy!",
            allowed_algorithms="RS256",
        ),
        database=DatabaseConfig(
            url="postgresql+psycopg://thali_user:a-secure-production-db-password-1234@db-prod.internal:5432/thali_production",
            pool_size=10,
            max_overflow=20,
            pool_timeout=5.0,
            pool_pre_ping=True,
        ),
        redis=RedisConfig(
            enabled=True,
            host="redis-prod.internal",
            port=6379,
            password="a-secure-redis-auth-token-with-sufficient-entropy",
        ),
        storage=StorageConfig(
            endpoint_url="https://s3.ap-south-1.amazonaws.com",
            bucket="thali-production-documents-ap-south-1",
            region="ap-south-1",
            access_key_id="AKIA-PROD-AUDIT-KEY-ID",
            secret_access_key="a-secure-s3-production-secret-key-entropy-40-chars",
        ),
        whatsapp=WhatsAppConfig(
            verify_token="a-secure-webhook-verify-token-production-16",
            app_secret="a-secure-whatsapp-production-secret-32-chars-long!",
            phone_number_id="100098765432100",
        ),
        observability=ObservabilityConfig(
            log_level="INFO",
            structured_logs=True,
            metrics_enabled=True,
            metrics_require_auth=True,
            metrics_auth_token="a-secure-metrics-scraping-token-entropy-16",
            tracing_enabled=True,
            tracing_exporter="otlp",
            tracing_otlp_endpoint="https://otel-collector.internal:4318/v1/traces",
        ),
        security=SecurityConfig(
            allowed_origins=[
                "https://admin.plate.thali.health",
                "https://plate.thali.health",
            ],
            session_ttl_minutes=60,
        ),
    )


def test_production_secrets_validation() -> None:
    print("==================================================================")
    print("Gate 10P-G — Production Secrets & Configuration Security Drill")
    print("==================================================================")

    # 1. Compliant configuration passes
    compliant = make_compliant_production_settings()
    validate_security_configuration(compliant)
    print("✓ Compliant production configuration successfully passed validation.")

    # 2. Missing client secret fails closed
    bad = make_compliant_production_settings()
    bad.identity.client_secret = ""
    try:
        validate_security_configuration(bad)
        sys.exit("FAIL: Empty client_secret did not fail closed!")
    except SecurityConfigurationError:
        print("✓ Empty client_secret fails closed (caught SecurityConfigurationError).")

    # 3. Insecure placeholder client secret fails closed
    bad = make_compliant_production_settings()
    bad.identity.client_secret = "dev-secret-change-in-production"
    try:
        validate_security_configuration(bad)
        sys.exit("FAIL: Insecure placeholder client_secret did not fail closed!")
    except SecurityConfigurationError:
        print("✓ Placeholder client_secret fails closed.")

    # 4. Short client secret (<32 chars) fails closed
    bad = make_compliant_production_settings()
    bad.identity.client_secret = "short-secret-1234567890"
    try:
        validate_security_configuration(bad)
        sys.exit("FAIL: Short client_secret did not fail closed!")
    except SecurityConfigurationError:
        print("✓ Short client_secret (<32 chars) fails closed.")

    # 5. Symmetric algorithm (HS256) in production fails closed
    bad = make_compliant_production_settings()
    bad.identity.allowed_algorithms = "HS256"
    try:
        validate_security_configuration(bad)
        sys.exit("FAIL: Symmetric algorithm in production did not fail closed!")
    except SecurityConfigurationError:
        print("✓ Symmetric algorithm (HS256) fails closed.")

    # 6. SQLite database in production fails closed
    bad = make_compliant_production_settings()
    bad.database.url = "sqlite:///prod.db"
    try:
        validate_security_configuration(bad)
        sys.exit("FAIL: SQLite in production did not fail closed!")
    except SecurityConfigurationError:
        print("✓ SQLite database in production fails closed.")

    # 7. Non-HTTPS issuer URL in production fails closed
    bad = make_compliant_production_settings()
    bad.identity.issuer_url = "http://auth.plate.thali.health/realms/thali-production"
    try:
        validate_security_configuration(bad)
        sys.exit("FAIL: Non-HTTPS issuer URL did not fail closed!")
    except SecurityConfigurationError:
        print("✓ Insecure HTTP issuer URL fails closed.")

    # 8. Missing Redis password when Redis enabled fails closed
    bad = make_compliant_production_settings()
    bad.redis.password = None
    try:
        validate_security_configuration(bad)
        sys.exit("FAIL: Missing Redis password did not fail closed!")
    except SecurityConfigurationError:
        print("✓ Missing Redis password fails closed.")

    # 9. Placeholder storage credentials (minioadmin) fails closed
    bad = make_compliant_production_settings()
    bad.storage.access_key_id = "minioadmin"
    bad.storage.secret_access_key = "minioadmin"
    try:
        validate_security_configuration(bad)
        sys.exit("FAIL: Placeholder minioadmin credentials did not fail closed!")
    except SecurityConfigurationError:
        print("✓ Placeholder storage credentials (minioadmin) fail closed.")

    # 10. Wildcard CORS origin (*) fails closed
    bad = make_compliant_production_settings()
    bad.security.allowed_origins = ["*"]
    try:
        validate_security_configuration(bad)
        sys.exit("FAIL: Wildcard CORS origin did not fail closed!")
    except SecurityConfigurationError:
        print("✓ Wildcard CORS origin ('*') fails closed.")

    print("\n==================================================================")
    print("ALL PRODUCTION SECRETS & CONFIGURATION CHECKS PASSED: 10/10")
    print("==================================================================")


if __name__ == "__main__":
    test_production_secrets_validation()
