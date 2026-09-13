"""HS256 JWT signature verification using only the standard library.

Implements RFC 7515 signing-input verification for the HMAC-SHA256 ("HS256")
alg with constant-time comparison. This is the cryptographic step that Gate 05
deliberately deferred from ``KeycloakTokenValidator``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass


class JwtSignatureError(ValueError):
    """Raised when a JWT cannot be cryptographically verified."""


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
