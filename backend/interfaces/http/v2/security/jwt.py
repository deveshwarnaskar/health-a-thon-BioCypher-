"""JWT signature verification (Gate 05 + Gate 10C-R).

HS256 path uses only the standard library and implements RFC 7515 signing-input
verification for the HMAC-SHA256 ("HS256") alg with constant-time comparison.
RS256 path delegates signature verification to PyJWT over an RSA public key
obtained from the Keycloak JWKS endpoint.

This module is the cryptographic step of the trust boundary. All failures raise
``TokenVerificationError`` (safe, non-sensitive message). No caller ever logs a
token, signing key, JWKS payload, or cryptographic detail.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

import jwt as pyjwt


class JwtSignatureError(ValueError):
    """Raised when a JWT cannot be cryptographically verified."""


class TokenVerificationError(ValueError):
    """Safe authentication failure for the HTTP boundary.

    The message NEVER contains JWT contents, signing keys, JWKS payloads, stack
    traces, internal crypto exceptions, or configuration secrets.
    """


@dataclass(frozen=True)
class Hs256Result:
    """Verified token parts (already signature-checked)."""

    header: dict
    payload: dict


def _b64_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise JwtSignatureError("malformed base64url segment") from exc


def jwt_header(token: str) -> dict:
    """Parse the JWT header segment without any signature verification.

    Used only to read the ``alg``/``kid`` claims so the verifier can select the
    correct policy and signing key. Raises ``JwtSignatureError`` on malformed
    structure; the parsed header is never trusted for authorization.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise JwtSignatureError("token must have three dot-separated segments")

    header_bytes = _b64_decode(parts[0])
    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except Exception as exc:
        raise JwtSignatureError("header is not valid JSON") from exc
    if not isinstance(header, dict):
        raise JwtSignatureError("malformed JWT header")
    return header


def verify_hs256(token: str, secret: str) -> Hs256Result:
    """Verify an HS256 JWT and return its header+payload if valid.

    Raises ``JwtSignatureError`` on any structural, algorithm, or signature
    mismatch. The comparison is constant-time (``hmac.compare_digest``).
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise JwtSignatureError("token must have three dot-separated segments")

    header_b64, payload_b64, signature_b64 = parts

    header_bytes = _b64_decode(header_b64)
    payload_bytes = _b64_decode(payload_b64)
    signature = _b64_decode(signature_b64)

    try:
        header = json.loads(header_bytes.decode("utf-8"))
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise JwtSignatureError("header/payload are not valid JSON") from exc

    alg = header.get("alg")
    if alg != "HS256":
        raise JwtSignatureError(f"unsupported alg '{alg}'; only HS256 is accepted")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_mac = hmac.new(
        secret.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()

    if len(signature) != len(expected_mac) or not hmac.compare_digest(
        signature, expected_mac
    ):
        raise JwtSignatureError("signature does not verify")

    return Hs256Result(header=header, payload=payload)


def verify_rs256(
    token: str,
    key,
    *,
    algorithms: list[str],
    audience: str,
    issuer: str,
) -> dict:
    """Verify an RS256 JWT against an RSA public key via PyJWT.

    ``algorithms`` is the explicit allow-list (never the token's own ``alg``).
    ``audience`` and ``issuer`` are enforced read from our configuration, not
    from the token. Raises ``TokenVerificationError`` with a safe message on
    any signature, structure, audience, issuer, or expiry failure.
    """
    if not audience:
        raise TokenVerificationError("audience is not configured")
    if not issuer:
        raise TokenVerificationError("issuer is not configured")
    try:
        return pyjwt.decode(
            token,
            key=key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise TokenVerificationError("authentication token has expired") from exc
    except pyjwt.InvalidAudienceError as exc:
        raise TokenVerificationError("token audience mismatch") from exc
    except pyjwt.InvalidIssuerError as exc:
        raise TokenVerificationError("token issuer mismatch") from exc
    except pyjwt.InvalidTokenError as exc:
        # Covers InvalidSignatureError, DecodeError, InvalidAlgorithmError and
        # every other PyJWT verification failure. Message never leaks details.
        raise TokenVerificationError("signature or token structure is invalid") from exc
