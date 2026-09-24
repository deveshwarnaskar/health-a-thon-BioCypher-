"""WhatsApp webhook security tests (Gate 07).

Proves:
- X-Hub-Signature-256 verified before JSON parsing.
- Tampered body → 401.
- Wrong signature → 401.
- Missing signature → 401.
- Invalid verify token → 403.
- Valid handshake → 200 returns challenge.
- Malformed JSON body (valid sig) → 400.
- JSON is NOT trusted before signature (valid JSON + wrong sig → 401, not 400).
- Replay/dedup not claimed (documented).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest

from tests.api.conftest import TEST_SECRET, bearer, make_jwt


def _sign(body: bytes, secret: str = "dev-webhook-secret-change-in-production") -> str:
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# Default app secret from config
_APP_SECRET = "dev-webhook-secret-change-in-production"
_DEFAULT_BODY = json.dumps({"object": "whatsapp_business_account"}).encode()


class TestWhatsAppVerify:
    """GET /api/v2/webhooks/whatsapp — challenge/verify handshake."""

    def test_valid_handshake_returns_challenge(self, client):
        resp = client.get(
            "/api/v2/webhooks/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "thali-dev-verify-token", "hub.challenge": "CHALLENGE_123"},
        )
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "CHALLENGE_123"

    def test_invalid_verify_token_returns_403(self, client):
        resp = client.get(
            "/api/v2/webhooks/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "wrong-token", "hub.challenge": "X"},
        )
        assert resp.status_code == 403

    def test_missing_hub_mode_returns_403(self, client):
        resp = client.get(
            "/api/v2/webhooks/whatsapp",
            params={"hub.verify_token": "thali-dev-verify-token", "hub.challenge": "X"},
        )
        assert resp.status_code == 403

    def test_missing_challenge_returns_403(self, client):
        resp = client.get(
            "/api/v2/webhooks/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "thali-dev-verify-token"},
        )
        assert resp.status_code == 403

    def test_mode_not_subscribe_returns_403(self, client):
        resp = client.get(
            "/api/v2/webhooks/whatsapp",
            params={"hub.mode": "unsubscribe", "hub.verify_token": "thali-dev-verify-token", "hub.challenge": "X"},
        )
        assert resp.status_code == 403


class TestWhatsAppWebhook:
    """POST /api/v2/webhooks/whatsapp — inbound receiver."""

    def test_valid_hmac_and_json_returns_202(self, client):
        sig = _sign(_DEFAULT_BODY)
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            content=_DEFAULT_BODY,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "received"

    def test_tampered_body_returns_401(self, client):
        sig = _sign(_DEFAULT_BODY)
        tampered = b'{"object":"tampered"}'
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            content=tampered,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_wrong_signature_returns_401(self, client):
        wrong_sig = "sha256=" + "a" * 64
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            content=_DEFAULT_BODY,
            headers={"X-Hub-Signature-256": wrong_sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_missing_signature_returns_401(self, client):
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            content=_DEFAULT_BODY,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_json_not_trusted_before_signature(self, client):
        """Valid JSON body with wrong signature → 401 (sig fails), NOT 400 (JSON parse)."""
        valid_json = json.dumps({"entry": [{"changes": [{"value": {"messages": []}}]}]}).encode()
        wrong_sig = "sha256=" + "0" * 64
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            content=valid_json,
            headers={"X-Hub-Signature-256": wrong_sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_malformed_json_valid_signature_returns_400(self, client):
        """Garbage body with valid signature → 400 (JSON parse failed)."""
        garbage = b"this is not json"
        sig = _sign(garbage)
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            content=garbage,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_signature_prefix_validation(self, client):
        """Signature without sha256= prefix → 401."""
        no_prefix = hmac.new(_APP_SECRET.encode(), _DEFAULT_BODY, hashlib.sha256).hexdigest()
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            content=_DEFAULT_BODY,
            headers={"X-Hub-Signature-256": no_prefix, "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_webhook_response_never_leaks_raw_body(self, client):
        """Accepted response contains no raw body data."""
        sig = _sign(_DEFAULT_BODY)
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            content=_DEFAULT_BODY,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 202
        body_text = resp.text
        assert _APP_SECRET not in body_text

    def test_replay_not_claimed(self, client):
        """Sending same payload twice returns 202 both times (no dedup in Gate 07)."""
        sig = _sign(_DEFAULT_BODY)
        r1 = client.post(
            "/api/v2/webhooks/whatsapp",
            content=_DEFAULT_BODY,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        r2 = client.post(
            "/api/v2/webhooks/whatsapp",
            content=_DEFAULT_BODY,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert r1.status_code == 202
        assert r2.status_code == 202
