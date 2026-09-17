"""Notification service (Gate 10L).

Orchestrates notification creation, server-derived recipient authorization,
transactional outbox publishing, and immutable audit logging.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from backend.application.ops.contracts import (
    SYSTEM_WORKER_ACTOR_ID,
    AuditAction,
    AuditEvent,
)
from backend.application.ops.ports import AuditStore
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.domain.entities import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from backend.domain.events.channel import ChannelMessageQueued
from backend.domain.exceptions import DomainError, EntityNotFound


class NotificationService:
    """Application service for tenant-scoped notifications."""

    def __init__(
        self,
        uow: UnitOfWork,
        events: DomainEventPublisher,
        audit: AuditStore,
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow = uow
        self._events = events
        self._audit = audit
        self._clock = clock
        self._id_gen = id_gen

    def send_notification(
        self,
        *,
        tenant_id: UUID,
        recipient_id: UUID,
        recipient_phone: str,
        template_name: str,
        template_params: dict[str, str],
        notification_type: NotificationType = NotificationType.REMINDER,
        channel: NotificationChannel = NotificationChannel.WHATSAPP,
        patient_id: UUID | None = None,
        scheduled_at: datetime | None = None,
        correlation_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> Notification:
        # 1. Patient active validation
        if patient_id is not None:
            try:
                patient = self._uow.patients.get(patient_id)
                if not patient.active:
                    raise DomainError(f"patient {patient_id} is deactivated; notifications cannot be sent")
            except EntityNotFound:
                raise DomainError(f"patient {patient_id} does not exist in this tenant")

        # 2. Recipient authorization validation
        if patient_id is not None and recipient_id != patient_id:
            # If recipient is not the patient, verify caregiver relationship if applicable
            rel = self._uow.caregiver_relationships.find_by_pair(recipient_id, patient_id)
            if rel is not None:
                if not rel.is_granted_at(self._clock.now()):
                    raise DomainError(
                        f"caregiver {recipient_id} relationship with patient {patient_id} is not verified or has expired"
                    )

        now = self._clock.now()
        is_immediate = scheduled_at is None or scheduled_at <= now
        status = NotificationStatus.QUEUED if is_immediate else NotificationStatus.PENDING

        notification = Notification(
            id=self._id_gen.new_uuid(),
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            recipient_phone=recipient_phone.strip(),
            patient_id=patient_id,
            notification_type=notification_type,
            channel=channel,
            template_name=template_name,
            template_params=template_params,
            status=status,
            created_at=now,
            scheduled_at=scheduled_at,
            correlation_id=correlation_id,
        )

        self._uow.notifications.add(notification)

        # 3. If immediate, enqueue to transactional outbox in same transaction
        if status == NotificationStatus.QUEUED:
            self._events.publish(
                ChannelMessageQueued(
                    message_id=notification.id,
                    channel_type=channel.value,
                    recipient_phone=recipient_phone.strip(),
                    template_name=template_name,
                    template_params=template_params,
                )
            )

        # 4. Record immutable compliance audit event
        self._audit.record(
            AuditEvent(
                tenant_id=tenant_id,
                actor_id=actor_id or SYSTEM_WORKER_ACTOR_ID,
                action=AuditAction.CREATE.value,
                resource_type="NOTIFICATION",
                resource_id=str(notification.id),
                correlation_id=str(correlation_id or ""),
                outcome="SUCCESS",
                provenance_metadata={
                    "channel": channel.value,
                    "template": template_name,
                    "recipient_id": str(recipient_id),
                    "notification_type": notification_type.value,
                },
            )
        )

        return notification
