"""WhatsApp webhook v2 routes (Gate 07).

GET  /api/v2/webhooks/whatsapp  — Meta challenge/verify-token handshake.
POST /api/v2/webhooks/whatsapp  — inbound verified event receiver.

POST processing order is strict:

    raw request bytes
        → X-Hub-Signature-256 verification (over raw bytes, constant-time)
        → only then JSON parsing
        → WhatsAppInboundEnvelope
        → OK acknowledgement

JSON is NEVER trusted before signature verification. Raw bodies are never
logged. Replay/idempotency is a Gate 09 contract and is NOT claimed here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from backend.interfaces.http.dependencies import get_whatsapp_app_secret, get_whatsapp_verify_token
from backend.interfaces.http.v2.webhooks.whatsapp.envelope import WhatsAppInboundEnvelope
from backend.interfaces.http.v2.webhooks.whatsapp.signature import (
    WebhookSignatureError,
    verify_x_hub_signature_256,
)
from backend.interfaces.http.v2.webhooks.whatsapp.verify_token import (
    VerifyTokenError,
    challenge_response,
)

webhook_router = APIRouter()


class WhatsAppVerifyResponse(BaseModel):
    challenge: str


class WhatsAppInboundResponse(BaseModel):
    status: str = "received"
    message: str = "Webhook event accepted for processing"


@webhook_router.get("/whatsapp", response_model=WhatsAppVerifyResponse)
async def whatsapp_verify(
    request: Request,
    verify_token: Annotated[str, Depends(get_whatsapp_verify_token)],
) -> WhatsAppVerifyResponse:
    """Meta webhook verification handshake (constant-time token comparison)."""
    hub_mode = request.query_params.get("hub.mode")
    hub_verify_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")
    try:
        challenge = challenge_response(
            hub_mode, hub_verify_token, hub_challenge, verify_token
        )
    except VerifyTokenError as exc:
        raise HTTPException(status_code=403, detail="Verification failed") from exc
    return WhatsAppVerifyResponse(challenge=challenge)


@webhook_router.post("/whatsapp", response_model=WhatsAppInboundResponse, status_code=202)
async def whatsapp_webhook(
    request: Request,
    app_secret: Annotated[str, Depends(get_whatsapp_app_secret)],
) -> WhatsAppInboundResponse:
    """Verify the provider signature over the RAW body, then parse JSON.

    Replay/idempotency/deduplication is deferred to Gate 09. This endpoint does
    NOT claim production-grade replay resistance.
    """
    raw_body = await request.body()

    signature_header = request.headers.get("X-Hub-Signature-256")
    try:
        verify_x_hub_signature_256(raw_body, signature_header, app_secret)
    except WebhookSignatureError as exc:
        raise HTTPException(status_code=401, detail="Webhook signature verification failed") from exc

    try:
        import json

        parsed = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON body") from exc

    entry = (parsed.get("entry") or [{}])[0]
    changes = entry.get("changes") or [{}]
    change = changes[0] if changes else {}
    value = change.get("value") or {}
    contacts = value.get("contacts") or [{}]
    messages = value.get("messages") or []

    message_id = ""
    source_phone = ""
    event_type = "message"
    if messages:
        message_id = messages[0].get("id", "")
        source_phone = messages[0].get("from", "")
        event_type = "message_received"
    elif contacts:
        source_phone = contacts[0].get("wa_id", "")

    envelope = WhatsAppInboundEnvelope.from_event(
        message_id=message_id,
        source_phone=source_phone,
        event_type=event_type,
    )
    # Envelope is only built AFTER signature verification. No raw body is logged.
    return WhatsAppInboundResponse(
        status="received",
        message="Webhook event accepted for processing",
    )