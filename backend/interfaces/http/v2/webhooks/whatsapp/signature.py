"""Webhook signature DSL and cryptographic verification boundary (Gate 06).

The webhook boundary verifies the WhatsApp provider signature over the RAW
request body bytes, never a re-serialized interpretation. Signature state is
frozen in an immutable envelope so no later component can observe a signature
that was only "accepted" — replay/idempotency guards key on provider message
ids, not on signature presence.

Uses only the standard library: ``hmac``, ``hashlib``, ``base64``, with
constant-time comparison via ``hmac.compare_digest``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac


class WebhookSignatureError(ValueError):
    """Raised when the provider webhook signature cannot be verified."""


def verify_x_hub_signature_256(
    raw_body: bytes, signature_header: str | None, secret: str
) -> None:
    """Verify the ``X-Hub-Signature-256`` header over the raw body bytes.

    The header carries a hex-encoded HMAC-SHA256 prefixed with ``sha256=``.
    Comparison is constant-time. The signature is the ONLY thing this boundary
    accepts — the body itself is never parsed here.
    """
    if not signature_header:
        raise WebhookSignatureError("missing X-Hub-Signature-256 header")

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        raise WebhookSignatureError("signature header must use the sha256= prefix")

    provided = signature_header[len(prefix) :]
    expected = hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(provided, expected):
        raise WebhookSignatureError("signature does not match the raw body")
