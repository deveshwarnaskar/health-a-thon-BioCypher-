"""Tests for Keycloak Identity Adapter Foundation (Gate 05).

Verifies:
1. Decoding unverified JWT tokens.
2. Claims extraction (sub, preferred_username, roles, tenant_id).
3. Expiration detection.
4. Issuer verification.
"""

import base64
import json
import time
from uuid import uuid4

import pytest

from backend.infrastructure.identity.keycloak_client import (
    KeycloakConfig,
    KeycloakTokenValidator,
)


def _make_dummy_jwt(payload: dict) -> str:
    header = {"alg": "RS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = "dummysig"
    return f"{header_b64}.{payload_b64}.{signature}"


def test_decode_and_validate_valid_token():
    user_id = uuid4()
    tenant_id = uuid4()
    config = KeycloakConfig(issuer_url="http://keycloak:8080/realms/thali")
    validator = KeycloakTokenValidator(config)

    token = _make_dummy_jwt({
        "sub": str(user_id),
        "preferred_username": "dr_sharma",
        "email": "sharma@hospital.org",
        "realm_access": {"roles": ["doctor", "clinician"]},
        "tenant_id": str(tenant_id),
        "iss": "http://keycloak:8080/realms/thali",
        "exp": time.time() + 3600,
    })

    claims = validator.validate_claims(token)
    assert claims.user_id == user_id
    assert claims.username == "dr_sharma"
    assert "doctor" in claims.roles
    assert claims.tenant_id == tenant_id


def test_expired_token_rejected():
    user_id = uuid4()
    config = KeycloakConfig()
    validator = KeycloakTokenValidator(config)

    expired_token = _make_dummy_jwt({
        "sub": str(user_id),
        "exp": time.time() - 100,
    })

    with pytest.raises(ValueError, match="Token has expired"):
        validator.validate_claims(expired_token)


def test_issuer_mismatch_rejected():
    user_id = uuid4()
    config = KeycloakConfig(issuer_url="http://keycloak:8080/realms/thali")
    validator = KeycloakTokenValidator(config)

    token = _make_dummy_jwt({
        "sub": str(user_id),
        "iss": "http://wrong-issuer.com",
        "exp": time.time() + 3600,
    })

    with pytest.raises(ValueError, match="Issuer mismatch"):
        validator.validate_claims(token)


def test_malformed_token_rejected():
    validator = KeycloakTokenValidator(KeycloakConfig())
    with pytest.raises(ValueError, match="Malformed JWT structure"):
        validator.validate_claims("invalid.token")
