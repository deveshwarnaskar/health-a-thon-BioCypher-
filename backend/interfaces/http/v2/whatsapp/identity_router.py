"""WhatsApp Identity and Connection Router (Gate 10P / WhatsApp Onboarding).

Provides server-authoritative WhatsApp identity lifecycle management:
- GET /api/v2/whatsapp/identity: get current connection status, masked phone, capabilities
- POST /api/v2/whatsapp/identity/request-verification: initiate OTP verification for a phone number
- POST /api/v2/whatsapp/identity/verify-code: verify OTP and link phone to patient record
- POST /api/v2/whatsapp/identity/disconnect: unlink phone from patient record
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.identity_patient_resolver import IdentityPatientResolver
from backend.domain.exceptions import EntityNotFound, InvalidPhoneNumber
from backend.domain.value_objects import PhoneNumber
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_clock,
    get_unit_of_work,
)
from backend.interfaces.http.ops.audit import audit_dependency
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.schemas.models import (
    WhatsAppIdentityResponse,
    WhatsAppRequestVerificationRequest,
    WhatsAppRequestVerificationResponse,
    WhatsAppVerifyCodeRequest,
)
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext

logger = logging.getLogger(__name__)

whatsapp_identity_router = APIRouter()

# Transient in-memory store for verification codes: (code, normalized_phone, expires_at_epoch)
_VERIFICATION_CODES: dict[str, tuple[str, str, float]] = {}

DEFAULT_CAPABILITIES = ["health_logging", "food_logging", "voice_messages"]


def _get_patient_for_actor(ctx: AuthenticatedContext, uow: UnitOfWork):
    if "patient" in ctx.roles:
        resolver = IdentityPatientResolver(uow)
        res = resolver.resolve(ctx.actor_id)
        if res.patient_id is not None:
            try:
                return uow.patients.get(res.patient_id)
            except EntityNotFound:
                return None
    elif "caregiver" in ctx.roles:
        rels = uow.caregiver_relationships.list_for_caregiver(ctx.actor_id)
        for r in rels:
            try:
                pat = uow.patients.get(r.patient_id)
                if pat.active:
                    return pat
            except Exception:
                continue
    return None


@whatsapp_identity_router.get(
    "/identity",
    response_model=WhatsAppIdentityResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="whatsapp.identity",
                atomic=False,
            )
        )
    ],
)
async def get_whatsapp_identity(
    request: Request,
    response: Response,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> WhatsAppIdentityResponse:
    """Return the authoritative WhatsApp connection status for the authenticated user/patient."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter, ctx=ctx)

    patient = _get_patient_for_actor(ctx, uow)
    if patient is not None and patient.phone is not None:
        return WhatsAppIdentityResponse(
            status="connected",
            phone_number=patient.phone.value,
            phone_number_masked=patient.phone.masked,
            verified_at=patient.created_at.isoformat() if hasattr(patient, "created_at") else None,
            capabilities=DEFAULT_CAPABILITIES,
        )

    return WhatsAppIdentityResponse(
        status="not_connected",
        phone_number=None,
        phone_number_masked=None,
        verified_at=None,
        capabilities=DEFAULT_CAPABILITIES,
    )


@whatsapp_identity_router.post(
    "/identity/request-verification",
    response_model=WhatsAppRequestVerificationResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.LOGIN,
                resource_type="whatsapp.request_verification",
                atomic=False,
            )
        )
    ],
)
async def request_whatsapp_verification(
    request: Request,
    response: Response,
    body: WhatsAppRequestVerificationRequest,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    clock: Annotated[Clock, Depends(get_clock)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> WhatsAppRequestVerificationResponse:
    """Request a 6-digit OTP verification code for the specified phone number."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter, ctx=ctx)

    try:
        phone = PhoneNumber(body.phone_number)
    except InvalidPhoneNumber as e:
        raise HTTPException(status_code=422, detail=f"Invalid phone number: {e}")

    # Generate 6-digit OTP code
    import secrets

    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = clock.now().timestamp() + 600.0  # 10 minutes

    cache_key = f"{ctx.tenant_id}:{ctx.actor_id}"
    _VERIFICATION_CODES[cache_key] = (code, phone.value, expires_at)

    logger.info(
        "Generated WhatsApp OTP for actor %s, phone %s: %s (expires in 600s)",
        ctx.actor_id,
        phone.masked,
        code,
    )

    return WhatsAppRequestVerificationResponse(
        success=True,
        phone_number=phone.value,
        expires_in_seconds=600,
        dev_code=code,
    )


@whatsapp_identity_router.post(
    "/identity/verify-code",
    response_model=WhatsAppIdentityResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.LOGIN,
                resource_type="whatsapp.verify_code",
                atomic=False,
            )
        )
    ],
)
async def verify_whatsapp_code(
    request: Request,
    response: Response,
    body: WhatsAppVerifyCodeRequest,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> WhatsAppIdentityResponse:
    """Verify the submitted 6-digit code and link the verified phone to the patient record."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter, ctx=ctx)

    try:
        phone = PhoneNumber(body.phone_number)
    except InvalidPhoneNumber as e:
        raise HTTPException(status_code=422, detail=f"Invalid phone number: {e}")

    cache_key = f"{ctx.tenant_id}:{ctx.actor_id}"
    stored = _VERIFICATION_CODES.get(cache_key)
    now = clock.now().timestamp()

    is_valid = False
    if stored is not None:
        stored_code, stored_phone, expires_at = stored
        if now <= expires_at and stored_code == body.code.strip() and stored_phone == phone.value:
            is_valid = True
            _VERIFICATION_CODES.pop(cache_key, None)

    # Standard testing bypass fallback: code "123456" accepted ONLY in non-production setups
    if not is_valid and body.code.strip() == "123456":
        from config.settings import Settings

        if (Settings().app.env or "").strip().lower() != "production":
            is_valid = True

    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    patient = _get_patient_for_actor(ctx, uow)
    if patient is None:
        raise HTTPException(status_code=404, detail="No active patient record associated with this account")

    patient.link_phone(phone)
    uow.patients.save(patient)

    # 1. Dispatch personalized structured welcome message with patient's name
    import uuid
    from config.settings import Settings
    from backend.domain.events.channel import ChannelMessageQueued
    from backend.infrastructure.channel.welcome_template import build_welcome_message
    from backend.infrastructure.channel.template_registry import WhatsAppTemplateRegistry
    from backend.infrastructure.persistence.uow.outbox_publisher import SqlAlchemyOutboxDomainEventPublisher

    welcome_template_name = WhatsAppTemplateRegistry(settings=Settings()).resolve_welcome_template()
    if welcome_template_name == "text":
        welcome_params = {"body": build_welcome_message(patient.name)}
    elif welcome_template_name in ("thali_welcome", "thali_welcome_greeting"):
        welcome_params = {"1": patient.name, "_language": "en"}
    else:
        welcome_params = {"_language": "en"}

    if welcome_template_name == "text":
        # No APPROVED template yet (free-form is only deliverable inside a 24h
        # customer-care window). Record a PENDING WELCOME marker so the channel
        # intake handler sends the greeting as soon as the window opens (i.e. the
        # newly-linked phone messages the business first). No direct/outbox attempt
        # here -- outside a window it is always rejected by Meta (131030).
        from backend.domain.entities import Notification, NotificationChannel, NotificationStatus, NotificationType

        try:
            uow.notifications.add(
                Notification(
                    tenant_id=ctx.tenant_id,
                    recipient_id=patient.id,
                    recipient_phone=phone.value,
                    patient_id=patient.id,
                    notification_type=NotificationType.WELCOME,
                    channel=NotificationChannel.WHATSAPP,
                    template_name="text",
                    template_params=welcome_params,
                    status=NotificationStatus.PENDING,
                    scheduled_at=None,
                )
            )
            logger.info("welcome deferred: no approved template; greeting queued for first inbound message")
        except Exception as exc:
            logger.warning("failed to record deferred welcome marker: %s", exc)
    else:
        # Approved template exists -> send greeting instantly at connect.
        try:
            session = getattr(uow, "_session", None)
            if session is not None:
                welcome_event = ChannelMessageQueued(
                    message_id=uuid.uuid4(),
                    tenant_id=ctx.tenant_id,
                    recipient_phone=phone.value,
                    channel_type="WHATSAPP",
                    template_name=welcome_template_name,
                    template_params=welcome_params,
                )
                SqlAlchemyOutboxDomainEventPublisher(session, tenant_id=ctx.tenant_id).publish(welcome_event)
        except Exception as exc:
            logger.warning("failed to enqueue welcome message to outbox: %s", exc)

    uow.commit()

    # 2. ALSO attempt immediate direct delivery via WhatsApp Cloud API (approved template path only)
    if welcome_template_name != "text":
        try:
            from backend.application.ops.contracts import OutboundMessage
            from backend.infrastructure.channel.whatsapp_sender import WhatsAppChannelSender

            sender = WhatsAppChannelSender()
            welcome_msg = OutboundMessage(
                message_id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                recipient_phone=phone.value,
                channel_type="WHATSAPP",
                template_name=welcome_template_name,
                template_params=welcome_params,
            )
            res = sender.send(welcome_msg)
            if not res.success:
                logger.warning("direct welcome message send deferred to worker: %s", res.error_code)
        except Exception as e:
            logger.info("direct welcome message dispatch skipped: %s", e)

    return WhatsAppIdentityResponse(
        status="connected",
        phone_number=patient.phone.value,
        phone_number_masked=patient.phone.masked,
        verified_at=clock.now().isoformat(),
        capabilities=DEFAULT_CAPABILITIES,
    )


@whatsapp_identity_router.post(
    "/identity/disconnect",
    response_model=WhatsAppIdentityResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.UPDATE,
                resource_type="whatsapp.disconnect",
                atomic=False,
            )
        )
    ],
)
async def disconnect_whatsapp(
    request: Request,
    response: Response,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> WhatsAppIdentityResponse:
    """Unlink the WhatsApp phone number from the patient record. Clinical records remain preserved."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter, ctx=ctx)

    patient = _get_patient_for_actor(ctx, uow)
    if patient is not None and patient.phone is not None:
        patient.unlink_phone()
        uow.patients.save(patient)
        uow.commit()

    return WhatsAppIdentityResponse(
        status="not_connected",
        phone_number=None,
        phone_number_masked=None,
        verified_at=None,
        capabilities=DEFAULT_CAPABILITIES,
    )
