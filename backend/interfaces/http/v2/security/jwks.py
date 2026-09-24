"""Keycloak RS256 signing-key retrieval and caching (Gate 10C-R).

Trust boundary requirements implemented here:

- ``jwks_uri`` comes from OIDC discovery metadata unless an explicit JWKS URI
  is configured (explicit configuration wins; the URL is never constructed by
  guesswork in production code).
- Keys are fetched and cached in-process with a TTL so token verification does
  not hit the network per request.
- The signing key is selected by ``kid`` (RFC 7517 key rotation).
- An unknown ``kid`` triggers exactly one cache refresh (rotation window); if
  the key still cannot be found the request fails CLOSED.
- Any discovery/JWKS retrieval failure raises ``JwtSignatureError`` — the HTTP
  boundary maps it to 401 and never leaks JWKS payloads or keys.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.interfaces.http.v2.security.jwt import JwtSignatureError, _b64_decode

_DEFAULT_CACHE_TTL_SECONDS = 300.0
_DISCOVERY_PATH = "/.well-known/openid-configuration"


async def fetch_json(url: str) -> dict[str, Any]:
    """Fetch a JSON document over HTTPS. Injectable seam for tests.

    Raises ``JwtSignatureError`` for a non-object document or when the
    endpoint is unreachable; no response content is ever logged.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        document = response.json()
    if not isinstance(document, dict):
        raise JwtSignatureError("JWKS endpoint returned a non-object document")
    return document


@dataclass(frozen=True)
class SigningKey:
    """A verified RSA signing key from the JWKS document."""

    kid: str
    algorithm: str
    public_key: rsa.RSAPublicKey


def _build_rsa_key(key: dict) -> rsa.RSAPublicKey:
    try:
        n = int.from_bytes(_b64_decode(str(key["n"])), "big")
        e = int.from_bytes(_b64_decode(str(key["e"])), "big")
    except (KeyError, TypeError, JwtSignatureError) as exc:
        raise JwtSignatureError("JWKS key is missing n/e material") from exc
    return rsa.RSAPublicNumbers(e=e, n=n).public_key()


class JwksClient:
    """Resolve, discover, cache and select Keycloak signing keys."""

    def __init__(
        self,
        *,
        issuer_url: str,
        jwks_uri: str = "",
        fetcher: Callable[[str], Awaitable[dict]] | None = None,
        cache_ttl: float = _DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._issuer_url = issuer_url.rstrip("/")
        self._explicit_jwks_uri = jwks_uri.rstrip("/")
        self._fetcher = fetcher if fetcher is not None else fetch_json
        self._cache_ttl = cache_ttl
        self._jwks_uri_cache: tuple[float, str] | None = None
        self._keys_cache: tuple[float, str, dict[str, SigningKey]] | None = None

    async def resolve_jwks_uri(self) -> str:
        """Return the JWKS endpoint (explicit config wins; else discovery)."""
        if self._explicit_jwks_uri:
            return self._explicit_jwks_uri

        if self._jwks_uri_cache is not None:
            fetched_at, uri = self._jwks_uri_cache
            if time.monotonic() - fetched_at < self._cache_ttl:
                return uri

        discovery_url = f"{self._issuer_url}{_DISCOVERY_PATH}"
        try:
            metadata = await self._fetcher(discovery_url)
        except JwtSignatureError:
            raise
        except Exception:
            raise JwtSignatureError("was not able to retrieve OIDC discovery metadata") from None

        uri = metadata.get("jwks_uri")
        if not isinstance(uri, str) or not uri:
            raise JwtSignatureError("OIDC discovery metadata did not expose jwks_uri")

        self._jwks_uri_cache = (time.monotonic(), uri)
        return uri

    async def signing_key(self, kid: str) -> SigningKey:
        """Return the signing key for ``kid``.

        Unknown ``kid`` triggers a single cache refresh to cover rotation;
        still missing (or repeated refresh failure) fails closed.
        """
        if not kid:
            raise JwtSignatureError("token is missing a key id")

        uri = await self.resolve_jwks_uri()
        keys = await self._keys(uri, force=False)

        key = keys.get(kid)
        if key is None:
            keys = await self._keys(uri, force=True)
            key = keys.get(kid)

        if key is None:
            raise JwtSignatureError("no signing key available for this token")
        return key

    async def _keys(self, uri: str, *, force: bool) -> dict[str, SigningKey]:
        cached = self._keys_cache
        if not force and cached is not None:
            fetched_at, cached_uri, keys = cached
            if cached_uri == uri and time.monotonic() - fetched_at < self._cache_ttl:
                return keys

        try:
            document = await self._fetcher(uri)
        except JwtSignatureError:
            raise
        except Exception:
            raise JwtSignatureError("was not able to retrieve JWKS document") from None

        raw_keys = document.get("keys")
        if not isinstance(raw_keys, list):
            raise JwtSignatureError("JWKS document did not contain a keys array")

        keys: dict[str, SigningKey] = {}
        for raw in raw_keys:
            if not isinstance(raw, dict):
                continue
            if raw.get("kty") != "RSA":
                continue
            use = raw.get("use")
            if use is not None and use != "sig":
                continue
            kid = raw.get("kid")
            if not kid:
                continue
            keys[str(kid)] = SigningKey(
                kid=str(kid),
                algorithm=str(raw.get("alg") or ""),
                public_key=_build_rsa_key(raw),
            )

        if not keys:
            raise JwtSignatureError("JWKS document contained no usable RSA signing keys")

        self._keys_cache = (time.monotonic(), uri, keys)
        return keys


__all__ = ["JwksClient", "SigningKey", "fetch_json"]