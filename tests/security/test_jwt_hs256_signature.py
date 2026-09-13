"""JWT HS256 signature verification boundary tests (Gate 06).

These lock the cryptographic step that Gate 05 deliberately deferred from
``KeycloakTokenValidator``: RFC 7515 signing-input verification for HS256,
constant-time, standard-library only. Every assertion is deterministic — no
network, no provider.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from backend.interfaces.http.v2.security import (
    Hs256Result,
    JwtSignatureError,
    verify_hs256,
)


def _b64(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sign(token_bytes_partial: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), token_bytes_partial, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")


def _hs256_token(secret: str, payload: dict, *, alg: str = "HS256") -> str:
    header = {"alg": alg, "typ": "JWT"}
    h, p = _b64(header), _b64(payload)
    return f"{h}.{p}.{_sign(f'{h}.{p}'.encode(), secret)}"


def test_verify_hs256_accepts_a_valid_token() -> None:
    secret = "realm-test-secret"
    token = _hs256_token(
        secret,
        {"sub": "u-1", "roles": ["doctor"], "tenant_id": "t-1", "exp": 4102444800},
    )

    result = verify_hs256(token, secret)

    assert isinstance(result, Hs256Result)
    assert result.payload["sub"] == "u-1"
    assert result.payload["roles"] == ["doctor"]
    assert result.header["alg"] == "HS256"


def test_verify_hs256_rejects_a_tampered_payload() -> None:
    secret = "realm-test-secret"
    token = _hs256_token(secret, {"sub": "u-1", "roles": ["doctor"]})
    _, payload_b64, signature = token.split(".")

    tampered_payload = _b64({"sub": "u-1", "roles": ["nurse"]})  # escalate role
    tampered = f"tampered.{payload_b64}.{signature}"

    with pytest.raises(JwtSignatureError):
        verify_hs256(tampered, secret)


def test_verify_hs256_rejects_a_wrong_secret() -> None:
    token = _hs256_token("realm-test-secret", {"sub": "u-1"})
    with pytest.raises(JwtSignatureError):
        verify_hs256(token, "a-different-secret")


def test_verify_hs256_rejects_unsupported_alg() -> None:
    token = _hs256_token("realm-test-secret", {"sub": "u-1"}, alg="RS256")
    with pytest.raises(JwtSignatureError):
        verify_hs256(token, "realm-test-secret")


def test_verify_hs256_rejects_malformed_token_structures() -> None:
    secret = "realm-test-secret"
    with pytest.raises(JwtSignatureError):
        verify_hs256("not-a-jwt", secret)  # no dot separation
    with pytest.raises(JwtSignatureError):
        verify_hs256("a.b.c.d", secret)  # too many segments


def test_verify_hs256_rejects_empty_secret_path() -> None:
    """An empty token or empty secret must never silently "verify"."""
    token = _hs256_token("realm-test-secret", {"sub": "u-1"})
    with pytest.raises(JwtSignatureError):
        verify_hs256("", "realm-test-secret")


def test_verify_hs256_serializes_fields_deterministically() -> None:
    """The same token + secret is a pure function (no non-determinism)."""
    secret = "realm-test-secret"
    token = _hs256_token(secret, {"sub": "u-1", "roles": ["doctor"]})
    first = verify_hs256(token, secret)
    second = verify_hs256(token, secret)
    assert first == second
    assert first.payload == second.payload
