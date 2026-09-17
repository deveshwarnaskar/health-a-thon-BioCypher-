"""Notifications v2 routes (Gate 10L).

Pure, assistive communication layer.
No clinical decision support, no glucose interpretation, no autonomous advice.
Protects information asymmetry: patient/caregiver projections never leak
clinical analytical fields (carbs_grams, glycemic_index, etc.).
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.application.ops.contracts import AuditAction, AuditEvent
from backend.application.ops.scheduler import ReminderScheduler
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.notification_service import NotificationService
from backend.domain.entities import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from backend.domain.entities.notification import FORBIDDEN_NOTIFICATION_FIELDS
from backend.domain.exceptions import DomainError, EntityNotFound
from backend.infrastructure.persistence.ops.audit_store import SqlAlchemyAuditStore
from backend.infrastructure.persistence.uow.outbox_publisher import (
    SqlAlchemyOutboxDomainEventPublisher,
)
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_clock,
    get_event_publisher,
    get_id_generator,
    get_unit_of_work,
)
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.schemas import (
    CreateNotificationRequest,
    NotificationListResponse,
    NotificationResponse,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
    is_proxy_role,
)
from backend.interfaces.http.v2.security.scoping import (
    assert_authorized_clinician_facility,
    authorize_or_403,
    authorize_patient_operation,
)

notifications_router = APIRouter()


def _correlation_id(request: Request) -> _uuid.UUID | None:
    raw = getattr(request.state, "correlation_id", None)
    if not raw:
        return None
    try:
        return _uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _notification_response(
    notif: Notification,
    *,
    is_patient_or_caregiver: bool = False,
) -> NotificationResponse:
    params = dict(notif.template_params or {})
    if is_patient_or_caregiver:
        params = {
            k: v for k, v in params.items()
            if k.lower() not in FORBIDDEN_NOTIFICATION_FIELDS
        }
    return NotificationResponse(
        id=str(notif.id),
        tenant_id=str(notif.tenant_id),
        recipient_id=str(notif.recipient_id),
        recipient_phone=notif.recipient_phone,
        patient_id=str(notif.patient_id) if notif.patient_id else None,
        notification_type=notif.notification_type.value if hasattr(notif.notification_type, "value") else str(notif.notification_type),
        channel=notif.channel.value if hasattr(notif.channel, "value") else str(notif.channel),
        template_name=notif.template_name,
        template_params=params,
        status=notif.status.value if hasattr(notif.status, "value") else str(notif.status),
        created_at=notif.created_at,
        scheduled_at=notif.scheduled_at,
        delivered_at=notif.delivered_at,
        failed_at=notif.failed_at,
        failure_reason=notif.failure_reason,
        correlation_id=str(notif.correlation_id) if notif.correlation_id else None,
        retry_count=notif.retry_count,
    )


@notifications_router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications",
    description="List notifications scoped by recipient, patient, or tenant with strict role-based access control.",
)
async def list_notifications(
    request: Request,
    response: Response,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    policy: Annotated[AuthorizationPolicy, Depends(get_authorization_policy)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
    patient_id: UUID | None = Query(default=None, description="Optional patient scope"),
    status: str | None = Query(default=None, description="Filter by status (pending, queued, delivered, failed)"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> NotificationListResponse:
    apply_rate_limit(
        request=request,
        response=response,
        tier=TIERS["read"],
        limiter=limiter,
        scope_key=str(ctx.actor_id),
    )

    is_proxy = is_proxy_role(ctx)
    items: list[Notification] = []

    if patient_id is not None:
        authorize_patient_operation(ctx, policy, Operation.READ_NOTIFICATIONS, patient_id, uow)
        raw_items = uow.notifications.list_for_patient(patient_id, limit=limit, offset=offset)
        if status:
            raw_items = [n for n in raw_items if n.status.value == status.lower()]
        items = raw_items
        total = len(items)
    elif "patient" in ctx.roles:
        # Patient listing without patient_id: find identity mapping
        mapping = uow.identity_mappings.get_by_user_id(ctx.actor_id)
        if mapping and mapping.active:
            try:
                p = uow.patients.get(mapping.patient_id)
                if not getattr(p, "active", True):
                    raise HTTPException(status_code=403, detail="Patient account deactivated")
                raw_items = uow.notifications.list_for_patient(mapping.patient_id, limit=limit, offset=offset)
            except EntityNotFound:
                raw_items = uow.notifications.list_for_recipient(ctx.actor_id, limit=limit, offset=offset)
        else:
            raw_items = uow.notifications.list_for_recipient(ctx.actor_id, limit=limit, offset=offset)

        if status:
            raw_items = [n for n in raw_items if n.status.value == status.lower()]
        items = raw_items
        total = len(items)
    elif "caregiver" in ctx.roles:
        # Caregiver listing own direct notifications
        raw_items = uow.notifications.list_for_recipient(ctx.actor_id, limit=limit, offset=offset)
        if status:
            raw_items = [n for n in raw_items if n.status.value == status.lower()]
        items = raw_items
        total = len(items)
    else:
        # Clinician / care team / admin
        authorize_or_403(ctx, policy, Operation.READ_NOTIFICATIONS)
        status_enum = None
        if status:
            try:
                status_enum = NotificationStatus(status.lower())
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid notification status: {status}")
        items = uow.notifications.list_for_tenant(status=status_enum, limit=limit, offset=offset)
        total = uow.notifications.count_for_tenant(status=status_enum)

    return NotificationListResponse(
        total=total,
        items=[
            _notification_response(n, is_patient_or_caregiver=is_proxy)
            for n in items
        ],
    )


@notifications_router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Get notification by ID",
)
async def get_notification(
    notification_id: UUID,
    request: Request,
    response: Response,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    policy: Annotated[AuthorizationPolicy, Depends(get_authorization_policy)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> NotificationResponse:
    apply_rate_limit(
        request=request,
        response=response,
        tier=TIERS["read"],
        limiter=limiter,
        scope_key=str(ctx.actor_id),
    )

    try:
        notif = uow.notifications.get(notification_id)
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc

    is_proxy = is_proxy_role(ctx)

    if "patient" in ctx.roles:
        # Must be recipient or mapped patient
        is_recipient = notif.recipient_id == ctx.actor_id
        is_mapped_patient = False
        if notif.patient_id:
            mapping = uow.identity_mappings.get_by_user_id(ctx.actor_id)
            if mapping and mapping.active and mapping.patient_id == notif.patient_id:
                patient = uow.patients.get(notif.patient_id)
                if not getattr(patient, "active", True):
                    raise HTTPException(status_code=403, detail="Patient account deactivated")
                is_mapped_patient = True
        if not (is_recipient or is_mapped_patient):
            raise HTTPException(status_code=403, detail="Access denied")

    elif "caregiver" in ctx.roles:
        is_recipient = notif.recipient_id == ctx.actor_id
        is_authorized_proxy = False
        if notif.patient_id:
            if policy.is_allowed(ctx, Operation.READ_NOTIFICATIONS, patient_id=notif.patient_id, uow=uow):
                is_authorized_proxy = True
        if not (is_recipient or is_authorized_proxy):
            raise HTTPException(status_code=403, detail="Access denied")

    else:
        # Clinician / care team / admin
        authorize_or_403(ctx, policy, Operation.READ_NOTIFICATIONS)
        if notif.patient_id:
            try:
                patient = uow.patients.get(notif.patient_id)
                assert_authorized_clinician_facility(ctx, uow, patient)
            except EntityNotFound:
                pass

    return _notification_response(notif, is_patient_or_caregiver=is_proxy)


@notifications_router.post(
    "",
    response_model=NotificationResponse,
    status_code=201,
    summary="Create and queue an operational notification",
)
async def create_notification(
    req: CreateNotificationRequest,
    request: Request,
    response: Response,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    policy: Annotated[AuthorizationPolicy, Depends(get_authorization_policy)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    events: Annotated[DomainEventPublisher, Depends(get_event_publisher)],
    clock: Annotated[Clock, Depends(get_clock)],
    id_gen: Annotated[IdGenerator, Depends(get_id_generator)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> NotificationResponse:
    apply_rate_limit(
        request=request,
        response=response,
        tier=TIERS["admin"],
        limiter=limiter,
        scope_key=str(ctx.actor_id),
    )

    authorize_or_403(ctx, policy, Operation.MANAGE_NOTIFICATIONS)

    # Validate recipient_id format
    try:
        recipient_id = UUID(req.recipient_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid recipient_id UUID") from exc

    patient_id: UUID | None = None
    if req.patient_id:
        try:
            patient_id = UUID(req.patient_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid patient_id UUID") from exc

    # Enforce information asymmetry: reject forbidden clinical analytics in template_params
    for key in req.template_params:
        if key.lower() in FORBIDDEN_NOTIFICATION_FIELDS:
            raise HTTPException(
                status_code=422,
                detail=f"Forbidden clinical field '{key}' cannot be used in notification template parameters",
            )

    try:
        notif_type = NotificationType(req.notification_type.lower())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid notification_type: {req.notification_type}")

    try:
        channel = NotificationChannel(req.channel.upper())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid channel: {req.channel}")

    audit = SqlAlchemyAuditStore(uow.session, ctx.tenant_id)
    cid = _correlation_id(request)

    service = NotificationService(
        uow=uow,
        events=events,
        audit=audit,
        clock=clock,
        id_gen=id_gen,
    )

    try:
        notif = service.send_notification(
            tenant_id=ctx.tenant_id,
            recipient_id=recipient_id,
            recipient_phone=req.recipient_phone,
            template_name=req.template_name,
            template_params=req.template_params,
            notification_type=notif_type,
            channel=channel,
            patient_id=patient_id,
            scheduled_at=req.scheduled_at,
            correlation_id=cid,
            actor_id=ctx.actor_id,
        )
        uow.commit()
    except DomainError as exc:
        uow.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        uow.rollback()
        raise

    return _notification_response(notif)


@notifications_router.post(
    "/process-due",
    summary="Process scheduled notifications that have come due",
)
async def process_due_notifications(
    request: Request,
    response: Response,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    policy: Annotated[AuthorizationPolicy, Depends(get_authorization_policy)],
    clock: Annotated[Clock, Depends(get_clock)],
    id_gen: Annotated[IdGenerator, Depends(get_id_generator)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, int]:
    apply_rate_limit(
        request=request,
        response=response,
        tier=TIERS["admin"],
        limiter=limiter,
        scope_key=str(ctx.actor_id),
    )

    authorize_or_403(ctx, policy, Operation.MANAGE_NOTIFICATIONS)

    engine = request.app.state.db_engine
    from sqlalchemy.orm import sessionmaker
    session_factory = sessionmaker(bind=engine)

    def uow_factory(tenant_id):
        return SqlAlchemyUnitOfWork(session_factory, tenant_id)

    def events_factory(uow):
        return SqlAlchemyOutboxDomainEventPublisher(uow.session, uow.tenant_id)

    def audit_factory(uow):
        return SqlAlchemyAuditStore(uow.session, uow.tenant_id)

    scheduler = ReminderScheduler(
        uow_factory=uow_factory,
        events_factory=events_factory,
        audit_factory=audit_factory,
        clock=clock,
        id_gen=id_gen,
    )

    processed = scheduler.process_due_notifications(ctx.tenant_id, limit=limit)
    return {"processed": processed}
