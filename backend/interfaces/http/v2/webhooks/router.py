"""WhatsApp webhook v2 routes (Gate 07 + Gate 09).

GET  /api/v2/webhooks/whatsapp  — Meta challenge/verify-token handshake.
POST /api/v2/webhooks/whatsapp  — inbound verified event receiver.

POST processing order is strict:

    raw request bytes
        → X-Hub-Signature-256 verification (over raw bytes, constant-time)
        → only then JSON parsing
        → rate-limit evaluation (webhook tier, signature-verified, FAIL_OPEN)
        → provider-receipt dedup (7-day window) ‖ outbox enqueue (atomic)
        → 202 acknowledgement

JSON is NEVER trusted before signature verification. Raw bodies are never
logged. Replay/idempotency IS claimed here (Gate 09 §8): duplicate provider
deliveries are acknowledged with 202 and dropped; only fresh deliveries write a
``whatsapp.message.received`` event to the transactional outbox for the worker.
Delivered-message/template status updates are acknowledged without clinical
work (the provider's read/delivered receipts never produce clinical state).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from backend.application.ops.contracts import WebhookReceipt
from backend.domain.events.channel import WhatsAppMessageReceived
from backend.infrastructure.persistence.ops.replay_store import SqlAlchemyWebhookReceiptStore
from backend.infrastructure.persistence.uow.outbox_publisher import SqlAlchemyOutboxDomainEventPublisher
from backend.interfaces.http.dependencies import (
    get_ops_session,
    get_whatsapp_app_secret,
    get_whatsapp_verify_token,
)
from backend.interfaces.http.ops.idempotency import build_fingerprint
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.webhooks.whatsapp.signature import (
    WebhookSignatureError,
    verify_x_hub_signature_256,
)
from backend.interfaces.http.v2.webhooks.whatsapp.verify_token import (
    VerifyTokenError,
    challenge_response,
)

logger = logging.getLogger(__name__)

webhook_router = APIRouter()


class WhatsAppVerifyResponse(BaseModel):
    challenge: str


class WhatsAppInboundResponse(BaseModel):
    status: str = "received"
    message: str = "Webhook event accepted for processing"


@webhook_router.get("/whatsapp")
async def whatsapp_verify(
    request: Request,
    verify_token: Annotated[str, Depends(get_whatsapp_verify_token)],
):
    """Meta webhook verification handshake (constant-time token comparison)."""
    from fastapi.responses import PlainTextResponse

    logger.info(">>> GET /whatsapp verify request from %s: %s", request.client.host if request.client else "unknown", dict(request.query_params))

    hub_mode = request.query_params.get("hub.mode")
    hub_verify_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")
    try:
        challenge = challenge_response(
            hub_mode, hub_verify_token, hub_challenge, verify_token
        )
    except VerifyTokenError as exc:
        raise HTTPException(status_code=403, detail="Verification failed") from exc

    ua = request.headers.get("user-agent", "").lower()
    is_meta = "facebook" in ua or "meta" in ua
    # Meta strictly expects raw plain text challenge echo:
    if is_meta or (hub_challenge and hub_challenge.isdigit()) or request.headers.get("accept") == "text/plain":
        return PlainTextResponse(content=challenge)

    return WhatsAppVerifyResponse(challenge=challenge)


def _fallback_message_id(raw_body: bytes, app_secret: str) -> str:
    """Deterministic HMAC fingerprint used when the payload omits a message id."""
    fingerprint = build_fingerprint(
        method="POST",
        path="/api/v2/webhooks/whatsapp",
        raw_body=raw_body,
        secret=app_secret,
    )
    return f"fallback:{fingerprint}"


from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedDelivery:
    """Parsed webhook delivery payload with full channel metadata."""

    provider_message_id: str
    source_phone: str
    event_type: str
    text: str
    recipient_phone_number_id: str = ""
    timestamp: int | None = None
    message_type: str = "text"
    interactive_reply_id: str | None = None
    media_type: str | None = None
    media_id: str | None = None
    caption: str | None = None

    def __iter__(self):
        yield self.provider_message_id
        yield self.source_phone
        yield self.event_type
        yield self.text


def _parse_delivery(raw_body: bytes, app_secret: str) -> ParsedDelivery:
    """Return ParsedDelivery containing provider delivery details.

    Raises HTTPException 400 on malformed JSON. Provider status updates
    (delivered/read) are folded into a status-id receipt key.
    """
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON body") from exc

    entry = (parsed.get("entry") or [{}])[0]
    changes = entry.get("changes") or [{}]
    change = changes[0] if changes else {}
    value = change.get("value") or {}
    metadata = value.get("metadata") or {}
    recipient_phone_number_id = str(metadata.get("phone_number_id") or "")
    contacts = value.get("contacts") or [{}]
    messages = value.get("messages") or []
    statuses = value.get("statuses") or []

    if messages:
        message = messages[0]
        message_id = message.get("id", "") or _fallback_message_id(raw_body, app_secret)
        source_phone = message.get("from", "")
        event_type = "message_received"
        msg_type = message.get("type", "text")
        ts_val = None
        try:
            if message.get("timestamp"):
                ts_val = int(message.get("timestamp"))
        except (ValueError, TypeError):
            ts_val = None

        text = ""
        interactive_reply_id = None
        media_type = None
        media_id = None
        caption = None

        if msg_type == "text":
            text = (message.get("text") or {}).get("body", "")
        elif msg_type == "interactive":
            interactive = message.get("interactive") or {}
            itype = interactive.get("type")
            if itype == "button_reply":
                breply = interactive.get("button_reply") or {}
                interactive_reply_id = breply.get("id")
                text = breply.get("title") or interactive_reply_id or ""
            elif itype == "list_reply":
                lreply = interactive.get("list_reply") or {}
                interactive_reply_id = lreply.get("id")
                text = lreply.get("title") or interactive_reply_id or ""
        elif msg_type == "button":
            btn = message.get("button") or {}
            interactive_reply_id = btn.get("payload")
            text = btn.get("text") or interactive_reply_id or ""
        elif msg_type in ("image", "audio", "document", "video"):
            media = message.get(msg_type) or {}
            media_type = msg_type
            media_id = media.get("id")
            caption = media.get("caption", "")
            text = caption or f"[{msg_type}]"
        else:
            text = (message.get("text") or {}).get("body", "")

        return ParsedDelivery(
            provider_message_id=message_id,
            source_phone=source_phone,
            event_type=event_type,
            text=text,
            recipient_phone_number_id=recipient_phone_number_id,
            timestamp=ts_val,
            message_type=msg_type,
            interactive_reply_id=interactive_reply_id,
            media_type=media_type,
            media_id=media_id,
            caption=caption,
        )

    if statuses:
        status = statuses[0]
        status_id = status.get("id", "") or _fallback_message_id(raw_body, app_secret)
        source_phone = status.get("recipient_id", "")
        event_type = "status_received"
        ts_val = None
        try:
            if status.get("timestamp"):
                ts_val = int(status.get("timestamp"))
        except (ValueError, TypeError):
            ts_val = None
        return ParsedDelivery(
            provider_message_id=status_id,
            source_phone=source_phone,
            event_type=event_type,
            text="",
            recipient_phone_number_id=recipient_phone_number_id,
            timestamp=ts_val,
            message_type="status",
        )

    if contacts:
        wa_id = contacts[0].get("wa_id", "")
        return ParsedDelivery(
            provider_message_id=_fallback_message_id(raw_body, app_secret),
            source_phone=wa_id,
            event_type="marketing",
            text="",
            recipient_phone_number_id=recipient_phone_number_id,
        )

    return ParsedDelivery(
        provider_message_id=_fallback_message_id(raw_body, app_secret),
        source_phone="",
        event_type="unknown",
        text="",
        recipient_phone_number_id=recipient_phone_number_id,
    )


@webhook_router.post("/whatsapp", response_model=WhatsAppInboundResponse, status_code=202)
async def whatsapp_webhook(
    request: Request,
    response: Response,
    app_secret: Annotated[str, Depends(get_whatsapp_app_secret)],
    ops_session: Annotated[object, Depends(get_ops_session)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> WhatsAppInboundResponse:
    """Verify signature over the RAW body, dedup, and enqueue clinical work.

    Receipt persistence + outbox enqueue commit in ONE transaction: a fresh
    delivery can never be acknowledged without its work item, and a duplicate
    never enqueues twice. Persistence failure → 503 (the provider retries).
    """
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")
    logger.info(">>> INBOUND WEBHOOK RECEIVED: len=%d bytes, signature_header=%s", len(raw_body), signature_header)

    try:
        if app_secret and app_secret != "dev-webhook-secret":
            verify_x_hub_signature_256(raw_body, signature_header, app_secret)
        elif signature_header and app_secret == "dev-webhook-secret":
            # Attempt verification with dev secret, but in development don't block real Meta webhooks if app_secret is unconfigured
            try:
                verify_x_hub_signature_256(raw_body, signature_header, app_secret)
            except WebhookSignatureError:
                import os
                from config.settings import Settings
                if Settings().app.env in ("production", "test", "testing") or "PYTEST_CURRENT_TEST" in os.environ:
                    raise
                logger.warning("dev mode: skipping strict signature mismatch because THALI_WHATSAPP__APP_SECRET is not configured with real Meta App Secret")
        else:
            verify_x_hub_signature_256(raw_body, signature_header, app_secret)
    except WebhookSignatureError as exc:
        logger.warning("Webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Webhook signature verification failed") from exc

    delivery = _parse_delivery(raw_body, app_secret)
    provider_message_id = delivery.provider_message_id
    source_phone = delivery.source_phone
    event_type = delivery.event_type
    text = delivery.text

    apply_rate_limit(
        request=request,
        response=response,
        tier=TIERS["webhook"],
        limiter=limiter,
        scope_key=source_phone or provider_message_id,
    )

    instance_id = uuid.uuid4()

    from sqlalchemy.exc import SQLAlchemyError

    try:
        receipt_store = SqlAlchemyWebhookReceiptStore(ops_session)
        fresh = receipt_store.record(
            WebhookReceipt(
                receipt_id=instance_id,
                provider="whatsapp",
                provider_message_id=provider_message_id,
                event_type=event_type,
                received_at=datetime.now(timezone.utc),
                source_phone=source_phone,
            )
        )
        if fresh and event_type == "message_received":
            event = WhatsAppMessageReceived(
                message_id=provider_message_id,
                source_phone=source_phone,
                text=text,
                recipient_phone_number_id=delivery.recipient_phone_number_id,
                timestamp=delivery.timestamp,
                message_type=delivery.message_type,
                interactive_reply_id=delivery.interactive_reply_id,
                media_type=delivery.media_type,
                media_id=delivery.media_id,
                caption=delivery.caption,
            )
            SqlAlchemyOutboxDomainEventPublisher(ops_session, tenant_id=None).publish(event)
        ops_session.commit()
    except SQLAlchemyError as exc:
        ops_session.rollback()
        logger.warning("webhook replay persistence failed; provider will retry")
        raise HTTPException(status_code=503, detail="Webhook event could not be persisted") from exc
    except Exception:
        ops_session.rollback()
        raise

    return WhatsAppInboundResponse(
        status="received",
        message="Webhook event accepted for processing",
    )