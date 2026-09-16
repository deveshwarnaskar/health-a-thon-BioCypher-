"""Gate 10C-R — RS256 crypto boundary and Keycloak JWKS client tests.

Covers:
- verify_rs256: valid / expired / bad signature / wrong issuer / wrong audience
  / tampered / malformed / algorithm-confusion (HS256 passed to RS256).
- jwt_header: structural parsing, fail-closed on malformed segments.
- JwksClient: explicit jwks_uri vs OIDC discovery, caching + TTL,
  kid-based selection, key rotation (unknown kid triggers exactly one refresh),
  fail-closed on unavailable JWKS / missing keys / unusable keys.
"""

from __future__ import annotations

import time
from uuid import uuid4

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.interfaces.http.v2.security.jwt import (
    JwtSignatureError,
    TokenVerificationError,
    jwt_header,
    verify_rs256,
)
from backend.interfaces.http.v2.security.jwks import JwksClient, SigningKey

RSA_PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
RSA_PUBLIC = RSA_PRIVATE.public_key()
KID_1 = "kid-1"
KID_2 = "kid-2"
AUDIENCE = "thali-backend"
ISSUER = "https://issuer.example/realms/thali"
JWKS_URI = "https://issuer.example/realms/thali/protocol/openid-connect/certs"
DISCOVERY_URL = "https://issuer.example/realms/thali/.well-known/openid-configuration"


def _b64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_jwk(kid: str, public_key=RSA_PUBLIC, *, use: str = "sig") -> dict:
    nums = public_key.public_numbers()
    n_bytes = nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")
    e_bytes = nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "use": use,
        "alg": "RS256",
        "kid": kid,
        "n": _b64url(n_bytes),
        "e": _b64url(e_bytes),
    }


def make_rs256_token(
    *,
    secret_key=RSA_PRIVATE,
    kid: str = KID_1,
    iss: str = ISSUER,
    aud= AUDIENCE,
    exp: float | None = time.time() + 3600,
    sub: str | None = None,
    extra: dict | None = None,
) -> str:
    payload: dict = {"iss": iss, "aud": aud, "sub": sub or str(uuid4())}
    if exp is not None:
        payload["exp"] = int(exp)
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, secret_key, algorithm="RS256", headers={"kid": kid})


class FakeFetch:
    """Deterministic fake for the JWKS/discovery fetcher with call log."""

    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = dict(responses)
        self.calls: list[str] = []

    async def __call__(self, url: str) -> object:
        self.calls.append(url)
        if url not in self._responses:
            raise RuntimeError("unreachable endpoint (simulated)")
        return self._responses[url]


# ─────────────────────────────────────────────────────────────────────────────
# verify_rs256 crypto boundary
# ─────────────────────────────────────────────────────────────────────────────


class TestVerifyRs256:
    def test_valid_token_returns_claims(self):
        sub = str(uuid4())
        claims = verify_rs256(
            make_rs256_token(sub=sub),
            RSA_PUBLIC,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
        )
        assert claims["sub"] == sub
        assert claims["iss"] == ISSUER
        assert claims["aud"] == AUDIENCE

    def test_expired_token_rejected(self):
        with pytest.raises(TokenVerificationError):
            verify_rs256(
                make_rs256_token(exp=time.time() - 3600),
                RSA_PUBLIC,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
            )

    def test_wrong_signature_key_rejected(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with pytest.raises(TokenVerificationError):
            verify_rs256(
                make_rs256_token(secret_key=other),
                RSA_PUBLIC,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
            )

    def test_wrong_issuer_rejected(self):
        with pytest.raises(TokenVerificationError):
            verify_rs256(
                make_rs256_token(iss="https://evil.example"),
                RSA_PUBLIC,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
            )

    def test_wrong_audience_rejected(self):
        with pytest.raises(TokenVerificationError):
            verify_rs256(
                make_rs256_token(aud="some-other-client"),
                RSA_PUBLIC,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
            )

    def test_audience_list_containing_expected_accepted(self):
        claims = verify_rs256(
            make_rs256_token(aud=[AUDIENCE, "https://gateway.example"]),
            RSA_PUBLIC,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
        )
        assert AUDIENCE in claims["aud"]

    def test_tampered_payload_rejected(self):
        token = make_rs256_token()
        header_b64, _, sig_b64 = token.split(".")
        # Re-encode the payload (with a different sub) and keep the original
        # signature — the signature must no longer verify.
        import base64
        import json

        tampered_payload = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": str(uuid4()),
            "exp": int(time.time()) + 3600,
        }
        tampered_payload_b64 = base64.urlsafe_b64encode(
            json.dumps(tampered_payload, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()
        with pytest.raises(TokenVerificationError):
            verify_rs256(
                f"{header_b64}.{tampered_payload_b64}.{sig_b64}",
                RSA_PUBLIC,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
            )

    def test_malformed_token_rejected(self):
        with pytest.raises(TokenVerificationError):
            verify_rs256(
                "not-a-jwt",
                RSA_PUBLIC,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
            )

    def test_hs256_token_not_accepted_by_rs256_verifier(self):
        """Algorithm confusion: an HS256 token must never verify as RS256."""
        hs_token = pyjwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": str(uuid4())},
            "shared-secret-long-enough-for-hmac-test-only",
            algorithm="HS256",
        )
        with pytest.raises(TokenVerificationError):
            verify_rs256(
                hs_token,
                RSA_PUBLIC,
                algorithms=["RS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
            )

    def test_missing_audience_configuration_fails_closed(self):
        with pytest.raises(TokenVerificationError):
            verify_rs256(
                make_rs256_token(),
                RSA_PUBLIC,
                algorithms=["RS256"],
                audience="",
                issuer=ISSUER,
            )


# ─────────────────────────────────────────────────────────────────────────────
# jwt_header
# ─────────────────────────────────────────────────────────────────────────────


class TestJwtHeader:
    def test_parses_valid_header(self):
        header = jwt_header(make_rs256_token())
        assert header["alg"] == "RS256"
        assert header["kid"] == KID_1

    def test_malformed_segment_count_rejected(self):
        with pytest.raises(JwtSignatureError):
            jwt_header("only.two")

    def test_non_json_header_rejected(self):
        import base64

        junk = base64.urlsafe_b64encode(b"not json").rstrip(b"=").decode()
        with pytest.raises(JwtSignatureError):
            jwt_header(f"{junk}.e30.e30")

    def test_non_dict_header_rejected(self):
        import base64

        arr = base64.urlsafe_b64encode(b'["x"]').rstrip(b"=").decode()
        with pytest.raises(JwtSignatureError):
            jwt_header(f"{arr}.e30.e30")


# ─────────────────────────────────────────────────────────────────────────────
# JwksClient
# ─────────────────────────────────────────────────────────────────────────────


def _client(fetcher, *, jwks_uri=JWKS_URI, issuer_url=ISSUER, cache_ttl=300.0):
    return JwksClient(issuer_url=issuer_url, jwks_uri=jwks_uri, fetcher=fetcher, cache_ttl=cache_ttl)


class TestJwksClient:
    def test_explicit_jwks_uri_wins_without_discovery(self):
        fetcher = FakeFetch({JWKS_URI: {"keys": [make_jwk(KID_1)]}})
        client = _client(fetcher)
        key = None

        async def run():
            nonlocal key
            key = await client.signing_key(KID_1)

        import asyncio

        asyncio.run(run())
        assert isinstance(key, SigningKey)
        assert key.kid == KID_1
        assert key.algorithm == "RS256"
        assert DISCOVERY_URL not in fetcher.calls

    def test_discovery_resolves_jwks_uri(self):
        fetcher = FakeFetch(
            {
                DISCOVERY_URL: {"issuer": ISSUER, "jwks_uri": JWKS_URI},
                JWKS_URI: {"keys": [make_jwk(KID_1)]},
            }
        )
        client = _client(fetcher, jwks_uri="")
        resolved = None

        async def run():
            nonlocal resolved
            resolved = await client.signing_key(KID_1)

        import asyncio

        asyncio.run(run())
        assert resolved is not None
        assert DISCOVERY_URL in fetcher.calls

    def test_discovery_missing_jwks_uri_fails_closed(self):
        fetcher = FakeFetch({DISCOVERY_URL: {"issuer": ISSUER}})
        client = _client(fetcher, jwks_uri="")

        async def run():
            await client.signing_key(KID_1)

        import asyncio

        with pytest.raises(JwtSignatureError):
            asyncio.run(run())

    def test_discovery_unreachable_fails_closed(self):
        fetcher = FakeFetch({})
        client = _client(fetcher, jwks_uri="")

        async def run():
            await client.signing_key(KID_1)

        import asyncio

        with pytest.raises(JwtSignatureError):
            asyncio.run(run())

    def test_keys_document_cached_within_ttl(self):
        fetcher = FakeFetch({JWKS_URI: {"keys": [make_jwk(KID_1)]}})
        client = _client(fetcher)

        async def run():
            return await client.signing_key(KID_1), await client.signing_key(KID_1)

        import asyncio

        asyncio.run(run())
        assert fetcher.calls.count(JWKS_URI) == 1

    def test_expired_cache_refetches(self):
        doc_fetcher = FakeFetch({JWKS_URI: {"keys": [make_jwk(KID_1)]}})
        # cache_ttl=0 ⇒ every lookup is a staleness refresh.
        client = _client(doc_fetcher, cache_ttl=0)

        async def run():
            await client.signing_key(KID_1)
            await client.signing_key(KID_1)

        import asyncio

        asyncio.run(run())
        assert doc_fetcher.calls.count(JWKS_URI) == 2

    def test_unknown_kid_triggers_single_refresh_then_fails_closed(self):
        """Unknown kid → exactly one refresh; still missing → fail closed."""
        fetcher = FakeFetch({JWKS_URI: {"keys": [make_jwk(KID_1)]}})
        client = _client(fetcher)

        async def run():
            await client.signing_key("kid-does-not-exist")

        import asyncio

        with pytest.raises(JwtSignatureError):
            asyncio.run(run())
        assert fetcher.calls.count(JWKS_URI) == 2  # initial + one refresh

    def test_key_rotation_unknown_kid_refresh_finds_new_key(self):
        """After rotation the refresh returns the new kid and succeeds."""
        fetcher = FakeFetch(
            {
                JWKS_URI: {
                    "keys": [make_jwk(KID_1)]
                }
            }
        )
        # Serve version 2 (both keys) from the second fetch onward.
        first = fetcher._responses[JWKS_URI]

        async def rotating(url: str):
            fetcher.calls.append(url)
            if fetcher.calls.count(url) >= 2:
                return {"keys": [make_jwk(KID_1), make_jwk(KID_2)]}
            return first

        client = JwksClient(
            issuer_url=ISSUER, jwks_uri=JWKS_URI, fetcher=rotating, cache_ttl=300.0
        )

        async def run():
            return await client.signing_key(KID_2)

        import asyncio

        key = asyncio.run(run())
        assert key.kid == KID_2
        assert fetcher.calls.count(JWKS_URI) == 2

    def test_refresh_failure_fails_closed(self):
        """A failing refresh must not downgrade the verification result."""
        fetcher = FakeFetch({JWKS_URI: {"keys": [make_jwk(KID_1)]}})
        first = fetcher._responses[JWKS_URI]

        async def failing_after_first(url: str):
            fetcher.calls.append(url)
            if fetcher.calls.count(url) >= 2:
                raise RuntimeError("jwks temporarily unavailable")
            return first

        client = JwksClient(issuer_url=ISSUER, jwks_uri=JWKS_URI, fetcher=failing_after_first)

        async def run():
            return await client.signing_key(KID_1)

        import asyncio

        # First lookup succeeds (cached); a subsequent unknown-kid lookup must
        # refresh and hit the failing endpoint → fail closed.
        asyncio.run(run())

        async def run_unknown():
            return await client.signing_key("kid-x")

        with pytest.raises(JwtSignatureError):
            asyncio.run(run_unknown())

    def test_encryption_keys_are_ignored(self):
        fetcher = FakeFetch(
            {
                JWKS_URI: {
                    "keys": [
                        make_jwk(KID_1, use="enc"),
                        make_jwk(KID_2),
                    ]
                }
            }
        )
        client = _client(fetcher)

        async def run():
            return await client.signing_key(KID_2)

        import asyncio

        key = asyncio.run(run())
        assert key.kid == KID_2

        async def run_enc():
            return await client.signing_key(KID_1)

        with pytest.raises(JwtSignatureError):
            asyncio.run(run_enc())

    def test_empty_keys_list_fails_closed(self):
        fetcher = FakeFetch({JWKS_URI: {"keys": []}})
        client = _client(fetcher)

        async def run():
            return await client.signing_key(KID_1)

        import asyncio

        with pytest.raises(JwtSignatureError):
            asyncio.run(run())

    def test_unreachable_jwks_fails_closed(self):
        fetcher = FakeFetch({})
        client = _client(fetcher)

        async def run():
            return await client.signing_key(KID_1)

        import asyncio

        with pytest.raises(JwtSignatureError):
            asyncio.run(run())