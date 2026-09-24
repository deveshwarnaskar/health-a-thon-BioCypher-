"""Authentication boundary tests (Gate 07).

Proves the full pipeline:

    Bearer <token>
        → extract
        → HS256 cryptographic verification (Gate 06 primitive)
        → trusted claims
        → issuer/expiry validation
        → AuthenticatedContext

Unverified claims never authorize a request.
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from tests.api.conftest import TEST_ISSUER, TEST_SECRET, bearer, make_jwt


class TestAuthentication:
    """Gate 07 — JWT authentication boundary."""

    def test_missing_bearer_returns_401(self, client):
        resp = client.get("/api/v2/auth/verify")
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, client):
        resp = client.get("/api/v2/auth/verify", headers=bearer("not-a-jwt"))
        assert resp.status_code == 401

    def test_invalid_signature_returns_401(self, client):
        token = make_jwt(
            sub=str(uuid4()),
            tenant_id=str(uuid4()),
            secret="wrong-secret-key",
        )
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, client):
        token = make_jwt(
            sub=str(uuid4()),
            tenant_id=str(uuid4()),
            exp=int(time.time()) - 1,
        )
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_unsupported_algorithm_returns_401(self, client):
        """verify_hs256 rejects non-HS256 algorithms."""
        header = '{"alg":"none","typ":"JWT"}'
        payload = '{"sub":"x","tenant_id":"x","iss":"x","exp":9999999999}'

        import base64
        h = base64.urlsafe_b64encode(header.encode()).rstrip(b"=").decode()
        p = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"{h}.{p}."  # no signature

        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_invalid_issuer_returns_401(self, client):
        token = make_jwt(
            sub=str(uuid4()),
            tenant_id=str(uuid4()),
            iss="http://wrong-issuer",
        )
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_missing_subject_returns_401(self, client):
        token = make_jwt(
            tenant_id=str(uuid4()),
            extra={"sub": None},
        )
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_missing_tenant_returns_401(self, client):
        header = {"alg": "HS256", "typ": "JWT"}
        payload_obj = {"sub": str(uuid4()), "iss": TEST_ISSUER, "exp": int(time.time()) + 3600}
        import json, base64
        h = base64.urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode()).rstrip(b"=").decode()
        p = base64.urlsafe_b64encode(json.dumps(payload_obj, separators=(",", ":")).encode()).rstrip(b"=").decode()
        sig = __import__("hmac").new(
            TEST_SECRET.encode(), f"{h}.{p}".encode(), __import__("hashlib").sha256
        ).digest()
        s = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        token = f"{h}.{p}.{s}"
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_malformed_tenant_id_returns_401(self, client):
        token = make_jwt(
            sub=str(uuid4()),
            tenant_id="not-a-uuid",
        )
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_valid_token_returns_200(self, client):
        sub = str(uuid4())
        tid = str(uuid4())
        fid = str(uuid4())
        token = make_jwt(
            sub=sub,
            tenant_id=tid,
            roles=["doctor"],
            facility_id=fid,
        )
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["actor_id"] == sub
        assert body["tenant_id"] == tid
        assert "doctor" in body["roles"]
        assert body["facility_id"] == fid

    def test_verify_never_returns_raw_jwt_or_secrets(self, client):
        """Verify endpoint returns only the four safe fields."""
        token = make_jwt(sub=str(uuid4()), tenant_id=str(uuid4()), roles=["nurse"])
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()
        allowed_keys = {"actor_id", "tenant_id", "roles", "facility_id"}
        assert set(body.keys()) == allowed_keys
        # Verify none of the values contain the secret
        body_str = str(body)
        assert TEST_SECRET not in body_str

    def test_token_with_empty_roles_returns_empty_list(self, client):
        token = make_jwt(sub=str(uuid4()), tenant_id=str(uuid4()))
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 200
        assert resp.json()["roles"] == []

    def test_malformed_role_claims_returns_401(self, client):
        import base64, json
        header = json.dumps({"alg": "HS256", "typ": "JWT"})
        payload = json.dumps({
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "iss": TEST_ISSUER,
            "exp": int(time.time()) + 3600,
            "realm_access": "not-a-list",
        })
        h = base64.urlsafe_b64encode(header.encode()).rstrip(b"=").decode()
        p = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        sig = __import__("hmac").new(
            TEST_SECRET.encode(), f"{h}.{p}".encode(), __import__("hashlib").sha256
        ).digest()
        s = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        token = f"{h}.{p}.{s}"
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401
