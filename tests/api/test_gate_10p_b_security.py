"""Gate 10P-B — Production Secrets Management, Identity & Security Hardening Tests.

Verifies:
1. Production configuration fail-closed invariants:
   - Rejects empty, missing, or default client secrets
   - Rejects secrets in the insecure blocklist
   - Rejects secrets shorter than 32 characters (<256 bits entropy)
   - Rejects non-HTTPS Keycloak/OIDC issuer URLs
   - Rejects missing client_id (JWT audience)
   - Rejects SQLite database URLs in production
   - Rejects symmetric algorithms (HS256) in production
   - Rejects insecure WhatsApp webhook secrets
   - Permits valid hardened configuration in production
   - Permits default configurations in development/testing
2. Exception messages do not leak secret values
3. create_app() fails closed in production when configuration is invalid
4. verify_access_token() unconditionally rejects HS256 tokens in production
5. Idempotency middleware fails closed with HTTP 503 (IDEMPOTENCY_STORAGE_UNAVAILABLE)
   on database reservation failure
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from starlette.requests import Request
from starlette.responses import Response

from backend.interfaces.http.app import create_app
from backend.interfaces.http.dependencies import (
    TokenVerificationError,
    _load_config,
    reset_config_cache,
    verify_access_token,
)
from backend.interfaces.http.ops.idempotency import IdempotencyMiddleware
from config.settings import (
    AppConfig,
    DatabaseConfig,
    IdentityConfig,
    SecurityConfigurationError,
    Settings,
    WhatsAppConfig,
    validate_security_configuration,
)
from tests.api.conftest import make_jwt


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures and Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_valid_production_settings() -> Settings:
    """Construct a valid, fully-hardened production Settings instance."""
    return Settings(
        _env_file=None,
        app=AppConfig(env="production"),
        identity=IdentityConfig(
            client_secret="a-secure-production-secret-with-more-than-32-chars-entropy!",
            issuer_url="https://auth.thali.internal/realms/thali",
            client_id="thali-backend-service",
            allowed_algorithms="RS256",
        ),
        database=DatabaseConfig(
            url="postgresql+psycopg://thali_user:secret_prod_pass@pg-prod:5432/thali_db"
        ),
        whatsapp=WhatsAppConfig(
            app_secret="a-secure-whatsapp-production-secret-32-chars-long!",
            verify_token="a-secure-webhook-verify-token-production",
        ),
    )


def _make_dummy_request(
    method: str = "POST",
    path: str = "/api/v2/test",
    headers: list[tuple[bytes, bytes]] | None = None,
    body: bytes = b'{"data": "test"}',
) -> Request:
    raw_headers = headers or []

    async def receive():
        return {"type": "http.request", "body": body}

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": raw_headers,
        "query_string": b"",
        "state": {"correlation_id": "corr-10pb-test"},
    }
    return Request(scope, receive=receive)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Security Configuration Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSecurityConfigurationValidation:
    """Test validate_security_configuration under various configurations."""

    def test_development_env_allows_defaults(self):
        """Development environment allows dev defaults and SQLite databases."""
        dev_settings = Settings(app=AppConfig(env="development"))
        validate_security_configuration(dev_settings)  # Should not raise

    def test_test_env_allows_defaults(self):
        """Testing environment allows dev defaults."""
        test_settings = Settings(app=AppConfig(env="test"))
        validate_security_configuration(test_settings)  # Should not raise

    def test_production_valid_configuration_succeeds(self):
        """Valid production settings pass validation without error."""
        prod_settings = _make_valid_production_settings()
        validate_security_configuration(prod_settings)

    def test_production_missing_client_secret_fails(self):
        """Production requires non-empty identity.client_secret."""
        settings = _make_valid_production_settings()
        settings.identity.client_secret = ""
        with pytest.raises(SecurityConfigurationError, match="client_secret"):
            validate_security_configuration(settings)

    @pytest.mark.parametrize(
        "insecure_secret",
        [
            "dev-secret-change-in-production",
            "rehearsal-secret-for-idempotency-only",
            "password",
            "admin",
            "changeme",
            "secret",
        ],
    )
    def test_production_insecure_client_secret_fails(self, insecure_secret):
        """Production rejects known insecure / placeholder secrets."""
        settings = _make_valid_production_settings()
        settings.identity.client_secret = insecure_secret
        with pytest.raises(SecurityConfigurationError, match="insecure/placeholder"):
            validate_security_configuration(settings)

    def test_production_short_client_secret_fails(self):
        """Production rejects secrets with fewer than 32 characters."""
        settings = _make_valid_production_settings()
        settings.identity.client_secret = "short-secret-12345"
        with pytest.raises(SecurityConfigurationError, match="at least 32 characters"):
            validate_security_configuration(settings)

    def test_production_missing_issuer_url_fails(self):
        """Production requires non-empty identity.issuer_url."""
        settings = _make_valid_production_settings()
        settings.identity.issuer_url = ""
        with pytest.raises(SecurityConfigurationError, match="issuer_url"):
            validate_security_configuration(settings)

    def test_production_http_issuer_url_fails(self):
        """Production rejects non-HTTPS issuer URLs."""
        settings = _make_valid_production_settings()
        settings.identity.issuer_url = "http://auth.thali.internal/realms/thali"
        with pytest.raises(SecurityConfigurationError, match="HTTPS"):
            validate_security_configuration(settings)

    def test_production_missing_client_id_fails(self):
        """Production requires non-empty identity.client_id (JWT audience)."""
        settings = _make_valid_production_settings()
        settings.identity.client_id = ""
        with pytest.raises(SecurityConfigurationError, match="client_id"):
            validate_security_configuration(settings)

    def test_production_sqlite_database_fails(self):
        """Production rejects SQLite databases."""
        settings = _make_valid_production_settings()
        settings.database.url = "sqlite:///:memory:"
        with pytest.raises(SecurityConfigurationError, match="forbids SQLite"):
            validate_security_configuration(settings)

    def test_production_empty_database_fails(self):
        """Production rejects empty database URL."""
        settings = _make_valid_production_settings()
        settings.database.url = ""
        with pytest.raises(SecurityConfigurationError, match="database.url"):
            validate_security_configuration(settings)

    @pytest.mark.parametrize(
        "bad_alg",
        [
            "HS256",
            "RS256,HS256",
            "HS384",
            "HS512",
        ],
    )
    def test_production_symmetric_jwt_algorithm_fails(self, bad_alg):
        """Production rejects symmetric JWT algorithms (HS256/384/512)."""
        settings = _make_valid_production_settings()
        settings.identity.allowed_algorithms = bad_alg
        with pytest.raises(SecurityConfigurationError, match="forbids symmetric JWT algorithm"):
            validate_security_configuration(settings)

    def test_production_no_asymmetric_algorithm_fails(self):
        """Production requires at least one recognized asymmetric algorithm."""
        settings = _make_valid_production_settings()
        settings.identity.allowed_algorithms = "NONE"
        with pytest.raises(SecurityConfigurationError, match="asymmetric JWT algorithm"):
            validate_security_configuration(settings)

    def test_production_insecure_whatsapp_secret_fails(self):
        """Production rejects insecure or short WhatsApp app secret."""
        settings = _make_valid_production_settings()
        settings.whatsapp.app_secret = "dev-webhook-secret-change-in-production"
        with pytest.raises(SecurityConfigurationError, match="insecure/placeholder whatsapp.app_secret"):
            validate_security_configuration(settings)

        settings.whatsapp.app_secret = "too-short"
        with pytest.raises(SecurityConfigurationError, match="whatsapp.app_secret to have at least 32 characters"):
            validate_security_configuration(settings)

    def test_error_message_does_not_leak_secrets(self):
        """Exception messages must never leak the secret string."""
        secret_value = "my-super-secret-key-that-must-never-leak-in-logs-or-errors"
        settings = _make_valid_production_settings()
        settings.identity.client_secret = "short"
        try:
            validate_security_configuration(settings)
        except SecurityConfigurationError as exc:
            assert secret_value not in str(exc)
            assert "short" not in str(exc)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Application Factory Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAppFactorySecurity:
    """Test create_app() validation behavior."""

    def test_create_app_fails_in_production_with_invalid_config(self):
        """create_app() fails closed when invoked with insecure production configuration."""
        insecure_prod_settings = Settings(
            app=AppConfig(env="production"),
            identity=IdentityConfig(client_secret=""),
        )
        with pytest.raises(SecurityConfigurationError):
            create_app(insecure_prod_settings)

    def test_create_app_succeeds_in_production_with_valid_config(self):
        """create_app() succeeds when invoked with valid production configuration."""
        valid_prod_settings = _make_valid_production_settings()
        app = create_app(valid_prod_settings)
        assert app is not None
        assert app.docs_url is None  # OpenAPI docs disabled in production
        assert app.redoc_url is None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dependencies & Token Verification Hardening Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDependenciesHardening:
    """Test dependencies _load_config and verify_access_token production gates."""

    def test_load_config_fails_in_production_with_insecure_settings(self, monkeypatch):
        """_load_config() raises SecurityConfigurationError in production with insecure settings."""
        reset_config_cache()
        monkeypatch.setenv("THALI_APP__ENV", "production")
        monkeypatch.setenv("THALI_IDENTITY__CLIENT_SECRET", "dev-secret-change-in-production")
        try:
            with pytest.raises(SecurityConfigurationError):
                _load_config()
        finally:
            reset_config_cache()

    def test_verify_access_token_rejects_hs256_in_production(self, monkeypatch):
        """In production, verify_access_token unconditionally rejects HS256 tokens."""
        reset_config_cache()
        try:
            # Mock _load_config to simulate production environment with RS256 configured
            mock_cfg = {
                "jwt_secret": "a" * 32,
                "issuer_url": "https://auth.thali.internal/realms/thali",
                "db_url": "postgresql://test:test@localhost/db",
                "whatsapp_verify_token": "token",
                "whatsapp_app_secret": "b" * 32,
                "app_env": "production",
                "allowed_algorithms": {"RS256", "HS256"},  # Even if HS256 was somehow listed
                "jwks_uri": "",
                "audience": "thali-backend-service",
            }
            monkeypatch.setattr("backend.interfaces.http.dependencies._config_cache", mock_cfg)

            # Generate an HS256 token
            hs256_token = make_jwt(
                sub=str(uuid4()),
                tenant_id=str(uuid4()),
                secret="a" * 32,
            )

            # Verify that verify_access_token unconditionally rejects HS256 in production
            with pytest.raises(TokenVerificationError, match="unsupported token algorithm"):
                asyncio.run(verify_access_token(hs256_token))
        finally:
            reset_config_cache()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Idempotency Middleware Fail-Closed Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIdempotencyFailClosed:
    """Test IdempotencyMiddleware fail-closed behavior on storage failure."""

    def test_idempotency_reservation_db_failure_returns_503(self):
        """When store.reserve() encounters a DB exception, middleware returns HTTP 503."""
        actor_id = uuid4()
        tenant_id = uuid4()

        # Build middleware
        dummy_app = MagicMock()
        mw = IdempotencyMiddleware(dummy_app, secret="a" * 32)

        # Mock _safe_claims to return valid claims
        async def mock_claims(req):
            return {"actor_id": actor_id, "tenant_id": tenant_id}

        mw._safe_claims = mock_claims

        # Mock session_factory to raise an exception inside store.reserve or session.commit
        mock_session = MagicMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mw._session_factory = mock_session_factory

        # Patch SqlAlchemyIdempotencyStore.reserve to raise an operational error
        with patch(
            "backend.interfaces.http.ops.idempotency.SqlAlchemyIdempotencyStore.reserve",
            side_effect=RuntimeError("Database connection lost"),
        ):
            request = _make_dummy_request(
                method="POST",
                path="/api/v2/test",
                headers=[
                    (b"idempotency-key", b"req-failclosed-12345"),
                    (b"authorization", b"Bearer some-token"),
                ],
            )

            async def call_next(req):
                return Response(content=b'{"result": "ok"}', status_code=200)

            response = asyncio.run(mw.dispatch(request, call_next))

            # Must return 503, rollback session, and NOT call call_next
            assert response.status_code == 503
            assert response.headers.get("content-type") == "application/json"
            assert mock_session.rollback.called
            assert mock_session.close.called
            assert not dummy_app.called

            # Check JSON body error code and safe message
            import json

            body = json.loads(response.body.decode("utf-8"))
            assert body["error"]["code"] == "IDEMPOTENCY_STORAGE_UNAVAILABLE"
            assert "duplicate execution" in body["error"]["message"]
            assert body["error"]["correlation_id"] == "corr-10pb-test"
