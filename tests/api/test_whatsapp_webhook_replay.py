"""Gate 09 API — WhatsApp webhook replay/outbox pipeline.

Proves the receiver contract §8 through the running app:

- A fresh, signature-verified message delivery writes exactly one
  ``whatsapp.message.received`` row to the transactional outbox and ACKs 202.
- A duplicate provider delivery (same provider_message_id) is ACKed 202 but
  never enqueues a second work item.
- Tampered / missing signatures are rejected 401 before any outbox write.
- A persistence failure surfaces as 503 so the provider retries.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.outbox_models import DomainEventOutboxModel
from backend.interfaces.http.dependencies import get_engine

_SECRET = "dev-webhook-secret-change-in-production"


def _sign(body: bytes) -> str:
    sig = hmac.new(_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _message_payload(message_id: str, text: str = "180") -> bytes:
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"display_phone_number": "15550000000"},
                                "messages": [
                                    {"from": "+919000000004", "id": message_id, "type": "text",
                                     "text": {"body": text}},
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    ).encode("utf-8")


def _outbox_rows(message_id: str) -> int:
    session = Session(get_engine())
    try:
        count = session.scalar(
            select(func.count())
            .select_from(DomainEventOutboxModel)
            .where(
                DomainEventOutboxModel.event_type == "whatsapp.message.received",
                DomainEventOutboxModel.payload.like(f"%{message_id}%"),
            )
        )
        return int(count or 0)
    finally:
        session.close()


def _post(client, body: bytes, *, sig: str | None = None) -> "object":
    headers = {"Content-Type": "application/json"}
    if sig is not None:
        headers["X-Hub-Signature-256"] = sig
    return client.post("/api/v2/webhooks/whatsapp", content=body, headers=headers)


class TestWhatsAppReplayPipeline:

    def test_fresh_delivery_acks_202_and_enqueues_once(self, client):
        body = _message_payload(f"wamid-fresh-{uuid4()}")
        resp = _post(client, body, sig=_sign(body))
        assert resp.status_code == 202
        assert resp.json()["status"] == "received"
        message_id = json.loads(body)["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
        assert _outbox_rows(message_id) == 1

    def test_duplicate_delivery_is_acknowledged_but_not_enqueued(self, client):
        message_id = f"wamid-dup-{uuid4()}"
        body = _message_payload(message_id)
        sig = _sign(body)
        first = _post(client, body, sig=sig)
        second = _post(client, body, sig=sig)
        assert first.status_code == 202
        assert second.status_code == 202
        assert _outbox_rows(message_id) == 1

    def test_tampered_signature_rejected_401_no_enqueue(self, client):
        body = _message_payload(f"wamid-tamper-{uuid4()}")
        tampered = _message_payload(f"wamid-tamper-{uuid4()}")
        resp = _post(client, tampered, sig=_sign(body))
        assert resp.status_code == 401
        message_id = json.loads(tampered)["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
        assert _outbox_rows(message_id) == 0

    def test_missing_signature_rejected_401(self, client):
        body = _message_payload(f"wamid-missing-{uuid4()}")
        resp = _post(client, body)
        assert resp.status_code == 401
        message_id = json.loads(body)["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
        assert _outbox_rows(message_id) == 0

    def test_persistence_failure_returns_503(self, client, monkeypatch):
        import backend.interfaces.http.v2.webhooks.router as router_module

        class _FailingPublisher:
            def __init__(self, *args, **kwargs):
                pass

            def publish(self, event):
                raise SQLAlchemyError("simulated persistence outage")

        monkeypatch.setattr(router_module, "SqlAlchemyOutboxDomainEventPublisher", _FailingPublisher)

        body = _message_payload(f"wamid-503-{uuid4()}")
        resp = _post(client, body, sig=_sign(body))
        assert resp.status_code == 503

    def test_unknown_event_type_acks_without_clinical_work(self, client):
        body = b'{"object": "whatsapp_business_account"}'
        assert _post(client, body, sig=_sign(body)).status_code == 202


__all__ = ["TestWhatsAppReplayPipeline"]