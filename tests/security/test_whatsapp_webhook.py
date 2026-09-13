"""WhatsApp inbound webhook boundary tests (Gate 06).

Verifies the three pieces of the verified inbound sequence in isolation:

1. ``X-Hub-Signature-256`` HMAC over the RAW body bytes (never re-serialized);
2. the verify-token handshake (constant-time, challenge echoed only on match);
3. normalization into the neutral ``WhatsAppInboundEnvelope``.

Symmetric test secrets are string constants — no network, no provider traffic.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from backend.interfaces.http.v2.webhooks.whatsapp import (
    WhatsAppInboundEnvelope,
    challenge_response,
    verify_x_hub_signature_256,
)
from backend.interfaces.http.v2.webhooks.whatsapp.signature import (
    WebhookSignatureError,
)
from backend.interfaces.http.v2.webhooks.whatsapp.verify_token import (
    VerifyTokenError,
)


def _hmac_sha256(b: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), b, hashlib.sha256).hexdigest()


def _signature_header(b: bytes, secret: str) -> str:
    return f"sha256={_hmac_sha256(b, secret)}"


def test_verify_x_hub_signature_256_accepts_valid_signature() -> None:
    raw = b'{"object":"whatsapp_business_account","entry":[]}'
    header = _signature_header(raw, "webhook-secret")
    verify_x_hub_signature_256(raw, header, "webhook-secret")  # must not raise


def test_verify_x_hub_signature_256_rejects_tampered_body() -> None:
    raw = b'{"object":"whatsapp_business_account","entry":[]}'
    header = _signature_header(raw, "webhook-secret")
    with pytest.raises(WebhookSignatureError):
        verify_x_hub_signature_256(raw + b"tampered", header, "webhook-secret")


def test_verify_x_hub_signature_256_rejects_wrong_secret() -> None:
    raw = b'{"object":"whatsapp_business_account","entry":[]}'
    header = _signature_header(raw, "webhook-secret")
    with pytest.raises(WebhookSignatureError):
        verify_x_hub_signature_256(raw, header, "another-secret")


def test_verify_x_hub_signature_256_rejects_missing_header() -> None:
    raw = b'{"object":"whatsapp_business_account","entry":[]}'
    with pytest.raises(WebhookSignatureError):
        verify_x_hub_signature_256(raw, None, "webhook-secret")


def test_verify_x_hub_signature_256_rejects_empty_header() -> None:
    raw = b'{"object":"whatsapp_business_account","entry":[]}'
    with pytest.raises(WebhookSignatureError):
        verify_x_hub_signature_256(raw, "", "webhook-secret")


def test_verify_x_hub_signature_256_rejects_wrong_prefix() -> None:
    raw = b'{"object":"whatsapp_business_account","entry":[]}'
    with pytest.raises(WebhookSignatureError):
        verify_x_hub_signature_256(raw, "md5=1234567890abcdef", "webhook-secret")


def test_challenge_response_echoes_challenge_for_valid_handshake() -> None:
    challenge = challenge_response(
        hub_verify_token="gate06-token-abc",
        configured_token="gate06-token-abc",
        hub_challenge="4759068381001",
        hub_mode="subscribe",
    )
    assert challenge == "4759068381001"


def test_challenge_response_rejects_token_mismatch() -> None:
    with pytest.raises(VerifyTokenError):
        challenge_response(
            hub_verify_token="attacker-token",
            configured_token="gate06-token-abc",
            hub_challenge="4759068381001",
            hub_mode="subscribe",
        )


def test_challenge_response_rejects_unsupported_mode() -> None:
    with pytest.raises(VerifyTokenError):
        challenge_response(
            hub_verify_token="gate06-token-abc",
            configured_token="gate06-token-abc",
            hub_challenge="4759068381001",
            hub_mode="unsubscribe",
        )


def test_envelope_normalizes_verified_inbound_event() -> None:
    envelope = WhatsAppInboundEnvelope.from_event(
        message_id="wamid.BAESEBVQ",
        source_phone="+919000000001",
        event_type="message",
    )
    assert envelope.message_id == "wamid.BAESEBVQ"
    assert envelope.source_phone == "+919000000001"
    assert envelope.event_type == "message"
    assert envelope.timestamp.tzinfo is not None
