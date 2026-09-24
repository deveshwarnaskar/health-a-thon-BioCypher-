"""Gate 10C-R — HTTP-layer RS256 boundary tests.

Proves the full production trust boundary through FastAPI TestClient:
- RS256 Keycloak-issued tokens (via JWKS) return 200 with correct context.
- Expired, bad-signature, wrong-issuer, wrong-audience, malformed tokens return 401.
- HS256 algorithm-confusion under RS256-only policy returns 401.
- Unknown kid → exactly one JWKS refresh → still missing → fail closed 401.
- Rotation window (new kid appears after refresh) → 200.
- JWKS retrieval failure → fail closed 401.
- Security: token contents and secrets never leak in 401 bodies.
- Idempotency middleware uses the same configured trust boundary.
- Default application algorithm policy is RS256 (no silent dual-accept).
"""

from __future__ import annotations

import asyncio
import time
from uuid import UUID, uuid4

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.requests import Request

from backend.interfaces.http.v2.security import jwks as jwks_module
from backend.interfaces.http.dependencies import reset_config_cache
from backend.interfaces.http.ops.idempotency import IdempotencyMiddleware
from config.settings import IdentityConfig
from tests.api.conftest import TEST_CLIENT_ID, TEST_ISSUER, TEST_SECRET, bearer

RSA_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
RSA_PUBLIC = RSA_PRIVATE.public_key()
KID = "test-key-1"
JWKS_URL = "https://issuer.example/test-jwks"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_jwk(kid: str = KID, public_key=RSA_PUBLIC) -> dict:
    nums = public_key.public_numbers()
    n_bytes = nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")
    e_bytes = nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64url(n_bytes),
        "e": _b64url(e_bytes),
    }


def make_rs256_token(
    *,
    sub: str | None = None,
    tenant_id: str | None = None,
    roles: list[str] | None = None,
    facility_id: str | None = None,
    exp: float | None = time.time() + 3600,
    iss: str | None = None,
    aud= None,
    kid: str = KID,
    private_key=RSA_PRIVATE,
    extra: dict | None = None,
) -> str:
    payload: dict = {
        "iss": iss if iss is not None else TEST_ISSUER,
        "aud": TEST_CLIENT_ID if aud is None else aud,
        "sub": sub or str(uuid4()),
        "tenant_id": tenant_id or str(uuid4()),
    }
    if exp is not None:
        payload["exp"] = int(exp)
    if roles is not None:
        payload["realm_access"] = {"roles": roles}
    if facility_id:
        payload["facility_id"] = facility_id
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


class FakeFetch:
    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = dict(responses)
        self.calls: list[str] = []

    async def __call__(self, url: str) -> object:
        self.calls.append(url)
        if url not in self._responses:
            raise RuntimeError("simulated fetch failure")
        return self._responses[url]


def _make_request(token: str = "") -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    scope: dict = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "path": "/api/v2/x",
        "raw_path": b"/api/v2/x",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
    }
    return Request(scope)


JWKS_DOC: dict = {"keys": [make_jwk(KID)]}


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: RS256-only policy + fake JWKS endpoint
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _rs256_policy(monkeypatch):
    """Override the default HS256 autouse config with the production RS256 policy."""
    monkeypatch.setenv("THALI_IDENTITY__ALLOWED_ALGORITHMS", "RS256")
    monkeypatch.setenv("THALI_IDENTITY__JWKS_URI", JWKS_URL)
    fake = FakeFetch({JWKS_URL: JWKS_DOC})
    reset_config_cache()
    monkeypatch.setattr(jwks_module, "fetch_json", fake)
    reset_config_cache()
    yield fake
    reset_config_cache()


@pytest.fixture
def client():
    from backend.interfaces.http.app import create_app
    from backend.interfaces.http.dependencies import get_engine
    from backend.infrastructure.persistence.models import Base

    Base.metadata.create_all(get_engine())
    from fastapi.testclient import TestClient
    return TestClient(create_app(), raise_server_exceptions=False)


# ─────────────────────────────────────────────────────────────────────────────
# HTTP-level RS256 verification
# ─────────────────────────────────────────────────────────────────────────────


class TestRs256HttpBoundary:
    def test_valid_rs256_token_returns_200(self, client):
        sub = str(uuid4())
        tid = str(uuid4())
        fid = str(uuid4())
        token = make_rs256_token(sub=sub, tenant_id=tid, roles=["doctor"], facility_id=fid)
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["actor_id"] == sub
        assert body["tenant_id"] == tid
        assert "doctor" in body["roles"]
        assert body["facility_id"] == fid

    def test_expired_returns_401(self, client):
        token = make_rs256_token(exp=time.time() - 3600)
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_wrong_signature_returns_401(self, client):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = make_rs256_token(private_key=other_key)
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_wrong_issuer_returns_401(self, client):
        token = make_rs256_token(iss="https://evil.example")
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_wrong_audience_returns_401(self, client):
        token = make_rs256_token(aud="some-other-client")
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_audience_list_accepted(self, client):
        token = make_rs256_token(aud=[TEST_CLIENT_ID, "https://gateway.example"])
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 200

    def test_missing_sub_returns_401(self, client):
        token = make_rs256_token(extra={"sub": ""})
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_missing_tenant_returns_401(self, client):
        token = make_rs256_token(extra={"tenant_id": None})
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_malformed_tenant_returns_401(self, client):
        token = make_rs256_token(tenant_id="not-a-uuid")
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, client):
        resp = client.get("/api/v2/auth/verify", headers=bearer("not-a-jwt"))
        assert resp.status_code == 401

    def test_hs256_confusion_returns_401(self, client):
        """An HS256 token must never be accepted when RS256 policy is active."""
        from tests.api.conftest import make_jwt
        token = make_jwt(sub=str(uuid4()), tenant_id=str(uuid4()))
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401

    def test_alg_none_returns_401(self, client):
        import base64
        import json
        h = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
        p = base64.urlsafe_b64encode(b'{"sub":"x"}').rstrip(b"=").decode()
        resp = client.get("/api/v2/auth/verify", headers=bearer(f"{h}.{p}."))
        assert resp.status_code == 401

    def test_unknown_kid_fails_closed(self, client, _rs256_policy):
        token = make_rs256_token(kid="kid-does-not-exist")
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 401
        assert _rs256_policy.calls.count(JWKS_URL) == 2  # initial + one refresh

    def test_key_rotation_success(self, client):
        """New kid appears after exactly one JWKS refresh."""
        fetcher = FakeFetch({JWKS_URL: {"keys": [make_jwk(KID)]}})
        first_doc = fetcher._responses[JWKS_URL]

        async def rotating(url: str):
            fetcher.calls.append(url)
            if fetcher.calls.count(url) >= 2:
                return {"keys": [make_jwk(KID), make_jwk("kid-new")]}
            return first_doc

        reset_config_cache()
        monkeypatched = rotating
        import backend.interfaces.http.v2.security.jwks as _mod
        _orig = _mod.fetch_json
        _mod.fetch_json = monkeypatched  # type: ignore[assignment]
        try:
            reset_config_cache()
            token = make_rs256_token(kid="kid-new")
            resp = client.get("/api/v2/auth/verify", headers=bearer(token))
            assert resp.status_code == 200
        finally:
            _mod.fetch_json = _orig
            reset_config_cache()

    def test_jwks_unavailable_fails_closed(self, client):
        reset_config_cache()
        import backend.interfaces.http.v2.security.jwks as _mod
        _orig = _mod.fetch_json

        async def fail(_url: str):
            raise RuntimeError("network down")

        _mod.fetch_json = fail  # type: ignore[assignment]
        try:
            reset_config_cache()
            token = make_rs256_token(kid="any-kid")
            resp = client.get("/api/v2/auth/verify", headers=bearer(token))
            assert resp.status_code == 401
        finally:
            _mod.fetch_json = _orig
            reset_config_cache()

    def test_token_contents_not_leaked_in_401(self, client):
        # Corrupt the signature of an otherwise well-formed token.
        token = make_rs256_token()
        header_b64, payload_b64, _ = token.split(".")
        bad_sig = _b64url(b"x" * 64)
        corrupted = f"{header_b64}.{payload_b64}.{bad_sig}"
        resp = client.get("/api/v2/auth/verify", headers=bearer(corrupted))
        assert resp.status_code == 401
        body = resp.text
        assert TEST_SECRET not in body
        assert TEST_ISSUER not in body
        assert bad_sig not in body
        assert payload_b64 not in body

    def test_verify_endpoint_returns_no_sensitive_fields(self, client):
        token = make_rs256_token(sub=str(uuid4()), tenant_id=str(uuid4()), roles=["nurse"])
        resp = client.get("/api/v2/auth/verify", headers=bearer(token))
        assert resp.status_code == 200
        allowed = {"actor_id", "tenant_id", "roles", "facility_id"}
        assert set(resp.json().keys()) == allowed
        assert TEST_SECRET not in str(resp.json())


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency middleware trust boundary (correction #1)
# ─────────────────────────────────────────────────────────────────────────────


class TestIdempotencyTrustBoundary:
    """Prove idempotency._safe_claims uses the SAME configured policy."""

    def test_valid_rs256_token_extracted(self):
        token = make_rs256_token()
        mw = IdempotencyMiddleware(lambda r: None, secret="fingerprint-secret")
        result = asyncio.run(mw._safe_claims(_make_request(token)))
        assert result is not None
        assert isinstance(result["actor_id"], UUID)
        assert isinstance(result["tenant_id"], UUID)

    def test_invalid_token_returns_none(self):
        mw = IdempotencyMiddleware(lambda r: None, secret="fingerprint-secret")
        result = asyncio.run(mw._safe_claims(_make_request("garbage")))
        assert result is None

    def test_hs256_token_returns_none_under_rs256_policy(self):
        """No independent legacy HS256 verification path in idempotency."""
        from tests.api.conftest import make_jwt
        token = make_jwt(sub=str(uuid4()), tenant_id=str(uuid4()))
        mw = IdempotencyMiddleware(lambda r: None, secret="fingerprint-secret")
        result = asyncio.run(mw._safe_claims(_make_request(token)))
        assert result is None

    def test_token_with_malformed_sub_returns_none(self):
        token = make_rs256_token(sub="not-a-uuid")
        mw = IdempotencyMiddleware(lambda r: None, secret="fingerprint-secret")
        result = asyncio.run(mw._safe_claims(_make_request(token)))
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Policy defaults
# ─────────────────────────────────────────────────────────────────────────────


class TestPolicyDefaults:
    def test_default_algorithm_is_rs256(self):
        assert IdentityConfig().allowed_algorithms == "RS256"

    def test_configured_policy_applied_when_no_override(self):
        """Without THALI_IDENTITY__ALLOWED_ALGORITHMS override the trust boundary is RS256."""
        import os
        os.environ.pop("THALI_IDENTITY__ALLOWED_ALGORITHMS", None)
        reset_config_cache()
        from backend.interfaces.http.dependencies import get_allowed_algorithms
        try:
            assert get_allowed_algorithms() == {"RS256"}
        finally:
            reset_config_cache()