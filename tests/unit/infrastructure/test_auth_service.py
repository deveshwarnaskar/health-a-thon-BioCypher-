"""Unit tests for custom authentication infrastructure (Task 1).

Tests:
- Password hashing and verification round trip (bcrypt)
- Password rejection on mismatch
- RS256 token generation and verification round trip
- Expired token rejection
- Refresh token issue and verification
- Refresh token rejection when access token passed
- Malformed token rejection
"""
from __future__ import annotations

import time
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.infrastructure.auth.password_service import hash_password, verify_password
from backend.infrastructure.auth.token_service import TokenService
from backend.interfaces.http.v2.security.jwt import TokenVerificationError


@pytest.fixture(scope="module")
def rsa_key_pair():
    """Generate ephemeral RSA key pair for testing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


@pytest.fixture
def token_service(rsa_key_pair):
    private_pem, public_pem = rsa_key_pair
    return TokenService(
        private_key_pem=private_pem,
        public_key_pem=public_pem,
        access_expire_minutes=60,
        refresh_expire_days=7,
    )


class TestPasswordService:
    def test_hash_verify_round_trip(self):
        plain = "SuperSecretPassword123!"
        hashed = hash_password(plain)
        assert hashed != plain
        assert hashed.startswith("$2b$")
        assert verify_password(plain, hashed) is True

    def test_wrong_password_rejected(self):
        plain = "CorrectPassword123!"
        hashed = hash_password(plain)
        assert verify_password("WrongPassword456!", hashed) is False

    def test_empty_or_corrupt_hash_returns_false(self):
        assert verify_password("secret", "not-a-valid-bcrypt-hash") is False
        assert verify_password("secret", "") is False


class TestTokenService:
    def test_access_token_issue_and_verify_round_trip(self, token_service):
        user_id = str(uuid4())
        tenant_id = str(uuid4())
        facility_id = str(uuid4())
        role = "doctor"

        token = token_service.issue_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            facility_id=facility_id,
        )
        assert isinstance(token, str)

        claims = token_service.verify_token(token)
        assert claims["sub"] == user_id
        assert claims["tenant_id"] == tenant_id
        assert claims["role"] == role
        assert claims["facility_id"] == facility_id
        assert claims["typ"] == "access"
        assert "exp" in claims
        assert "iat" in claims
        assert "jti" in claims

    def test_refresh_token_issue_and_verify(self, token_service):
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        token = token_service.issue_refresh_token(user_id=user_id, tenant_id=tenant_id)
        claims = token_service.verify_refresh_token(token)
        assert claims["sub"] == user_id
        assert claims["tenant_id"] == tenant_id
        assert claims["typ"] == "refresh"

    def test_verify_refresh_token_rejects_access_token(self, token_service):
        user_id = str(uuid4())
        tenant_id = str(uuid4())

        access_token = token_service.issue_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role="admin",
        )
        with pytest.raises(TokenVerificationError) as exc_info:
            token_service.verify_refresh_token(access_token)
        assert "not a refresh token" in str(exc_info.value)

    def test_expired_token_rejected(self, rsa_key_pair):
        private_pem, public_pem = rsa_key_pair
        # Create service with negative expiration to force expired token
        expiring_service = TokenService(
            private_key_pem=private_pem,
            public_key_pem=public_pem,
            access_expire_minutes=-10,
        )
        token = expiring_service.issue_access_token(
            user_id=str(uuid4()),
            tenant_id=str(uuid4()),
            role="patient",
        )
        with pytest.raises(TokenVerificationError) as exc_info:
            expiring_service.verify_token(token)
        assert "token has expired" in str(exc_info.value)

    def test_malformed_token_rejected(self, token_service):
        with pytest.raises(TokenVerificationError):
            token_service.verify_token("gibberish-not-a-jwt")
