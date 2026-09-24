"""Deterministic reminder and scheduler engine (Gate 10L).

Executes scheduled workflow checks and reminder notifications strictly deterministically.
No clinical decision support, no glucose interpretation, no medication titration,
and no autonomous clinical advice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from backend.application.ops.contracts import (
    SYSTEM_WORKER_ACTOR_ID,
    SYSTEM_WORKER_ACTOR_TYPE,
    AuditAction,
    AuditEvent,
)
from backend.application.ops.ports import AuditStore
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.domain.entities import (
    CareTaskStatus,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from backend.domain.events.channel import ChannelMessageQueued

logger = logging.getLogger(__name__)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReminderScheduler:
    """Deterministic reminder scheduling for operational and workflow events."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[UUID], UnitOfWork],
        events_factory: Callable[[UnitOfWork], DomainEventPublisher],
        audit_factory: Callable[[UnitOfWork], AuditStore],
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow_factory = uow_factory
        self._events_factory = events_factory
        self._audit_factory = audit_factory
        self._clock = clock
        self._id_gen = id_gen

    def process_due_notifications(self, tenant_id: UUID, *, limit: int = 50) -> int:
        """Process notifications that were scheduled and have now come due."""
        uow = self._uow_factory(tenant_id)
        events = self._events_factory(uow)
        audit = self._audit_factory(uow)
        now = self._clock.now()
        processed_count = 0

        try:
            due_notifications = uow.notifications.list_due(before=now, limit=limit)
            for notif in due_notifications:
                notif.queue()
                uow.notifications.save(notif)

                events.publish(
                    ChannelMessageQueued(
                        message_id=notif.id,
                        channel_type=notif.channel.value,
                        recipient_phone=notif.recipient_phone,
                        template_name=notif.template_name,
                        template_params=notif.template_params,
                    )
                )

                audit.record(
                    AuditEvent(
                        tenant_id=tenant_id,
                        actor_id=SYSTEM_WORKER_ACTOR_ID,
                        actor_type=SYSTEM_WORKER_ACTOR_TYPE,
                        action=AuditAction.UPDATE.value,
                        resource_type="NOTIFICATION",
                        resource_id=str(notif.id),
                        outcome="SUCCESS",
                        provenance_metadata={"trigger": "scheduler_due_dispatch"},
                    )
                )
                processed_count += 1

            if processed_count > 0:
                uow.commit()
            return processed_count
        finally:
            uow.close()

    def schedule_care_task_due_reminders(
        self,
        tenant_id: UUID,
        *,
        window_hours: int = 24,
        limit: int = 50,
    ) -> int:
        """Create deterministic reminders for upcoming due care tasks."""
        uow = self._uow_factory(tenant_id)
        events = self._events_factory(uow)
        audit = self._audit_factory(uow)
        now = self._clock.now()
        horizon = now + timedelta(hours=window_hours)
        scheduled_count = 0

        try:
            candidate_tasks = []
            if hasattr(uow.care_tasks, "list_for_tenant"):
                candidate_tasks = uow.care_tasks.list_for_tenant()
            else:
                for patient in uow.patients.list():
                    candidate_tasks.extend(uow.care_tasks.list_for_patient(patient.id))

            for task in candidate_tasks:
                if scheduled_count >= limit:
                    break
                if task.status not in (CareTaskStatus.OPEN, CareTaskStatus.IN_PROGRESS):
                    continue
                task_due = _aware(task.due_at)
                if not task_due or not (now <= task_due <= horizon):
                    continue

                # Idempotency check: see if a notification for this task was already scheduled
                existing = uow.notifications.list_for_recipient(task.assigned_to_user_id, limit=50)
                already_scheduled = any(
                    n.template_params.get("task_id") == str(task.id)
                    and n.status in (NotificationStatus.PENDING, NotificationStatus.QUEUED, NotificationStatus.DELIVERED)
                    for n in existing
                )
                if already_scheduled:
                    continue

                # Create reminder notification
                notif = Notification(
                    id=self._id_gen.new_uuid(),
                    tenant_id=tenant_id,
                    recipient_id=task.assigned_to_user_id,
                    recipient_phone="",
                    patient_id=task.patient_id,
                    notification_type=NotificationType.TASK_ASSIGNED,
                    channel=NotificationChannel.IN_APP,
                    template_name="care_task_due_reminder",
                    template_params={
                        "task_id": str(task.id),
                        "description": task.description,
                        "due_at": task.due_at.isoformat(),
                    },
                    status=NotificationStatus.QUEUED,
                    created_at=now,
                )
                uow.notifications.add(notif)
                audit.record(
                    AuditEvent(
                        tenant_id=tenant_id,
                        actor_id=SYSTEM_WORKER_ACTOR_ID,
                        actor_type=SYSTEM_WORKER_ACTOR_TYPE,
                        action=AuditAction.CREATE.value,
                        resource_type="NOTIFICATION",
                        resource_id=str(notif.id),
                        outcome="SUCCESS",
                        provenance_metadata={"trigger": "scheduler_task_reminder", "task_id": str(task.id)},
                    )
                )
                scheduled_count += 1

            if scheduled_count > 0:
                uow.commit()
            return scheduled_count
        finally:
            uow.close()

    def schedule_medication_adherence_reminder(
        self,
        tenant_id: UUID,
        *,
        patient_id: UUID,
        medication_plan_id: UUID,
        scheduled_at: datetime | None = None,
    ) -> Notification:
        """Create deterministic adherence check reminder for an active clinician-authored plan."""
        uow = self._uow_factory(tenant_id)
        events = self._events_factory(uow)
        audit = self._audit_factory(uow)
        now = self._clock.now()

        try:
            patient = uow.patients.get(patient_id)
            if not patient.active:
                raise ValueError("Cannot schedule reminder for deactivated patient")

            plan = uow.medication_plans.get(medication_plan_id)
            if not plan.active:
                raise ValueError("Cannot schedule reminder for inactive medication plan")

            # Determine recipient phone
            recipient_phone = patient.phone.value if patient.phone else ""

            is_immediate = scheduled_at is None or scheduled_at <= now
            status = NotificationStatus.QUEUED if is_immediate else NotificationStatus.PENDING

            notif = Notification(
                id=self._id_gen.new_uuid(),
                tenant_id=tenant_id,
                recipient_id=patient.id,
                recipient_phone=recipient_phone,
                patient_id=patient.id,
                notification_type=NotificationType.REMINDER,
                channel=NotificationChannel.WHATSAPP if recipient_phone else NotificationChannel.IN_APP,
                template_name="medication_adherence_check",
                template_params={
                    "plan_id": str(plan.id),
                    "medication": plan.medication,
                    "instruction": plan.instruction,
                },
                status=status,
                created_at=now,
                scheduled_at=scheduled_at,
            )
            uow.notifications.add(notif)

            if status == NotificationStatus.QUEUED and notif.channel == NotificationChannel.WHATSAPP:
                events.publish(
                    ChannelMessageQueued(
                        message_id=notif.id,
                        channel_type=notif.channel.value,
                        recipient_phone=recipient_phone,
                        template_name=notif.template_name,
                        template_params=notif.template_params,
                    )
                )

            audit.record(
                AuditEvent(
                    tenant_id=tenant_id,
                    actor_id=SYSTEM_WORKER_ACTOR_ID,
                    actor_type=SYSTEM_WORKER_ACTOR_TYPE,
                    action=AuditAction.CREATE.value,
                    resource_type="NOTIFICATION",
                    resource_id=str(notif.id),
                    outcome="SUCCESS",
                    provenance_metadata={"trigger": "scheduler_medication_reminder", "plan_id": str(plan.id)},
                )
            )
            uow.commit()
            return notif
        finally:
            uow.close()

    def schedule_caregiver_companion_nudges(
        self,
        tenant_id: UUID,
        *,
        limit: int = 50,
        force_milestone: Any | None = None,
    ) -> int:
        """Evaluate chronobiological proactive caregiver touchpoints for tenant's patients.

        Dispatches empathetic, human-like health companion nudges via WhatsApp
        while strictly suppressing duplicates, honoring quiet hours, and respecting
        clinical information asymmetry.
        """
        from backend.application.services.caregiver_companion import evaluate_patient_caregiver_nudge

        uow = self._uow_factory(tenant_id)
        events = self._events_factory(uow)
        audit = self._audit_factory(uow)
        now = self._clock.now()
        scheduled_count = 0

        try:
            patients = uow.patients.list() if hasattr(uow.patients, "list") else []
            for patient in patients:
                if scheduled_count >= limit:
                    break
                if not getattr(patient, "active", True):
                    continue

                nudge = evaluate_patient_caregiver_nudge(
                    patient,
                    uow,
                    now_utc=now,
                    force_milestone=force_milestone,
                )
                if nudge is None:
                    continue

                notif = Notification(
                    id=self._id_gen.new_uuid(),
                    tenant_id=tenant_id,
                    recipient_id=patient.id,
                    recipient_phone=nudge.recipient_phone,
                    patient_id=patient.id,
                    notification_type=NotificationType.REMINDER,
                    channel=NotificationChannel.WHATSAPP,
                    template_name="text",
                    template_params={
                        "body": nudge.message_text,
                        "milestone": nudge.milestone.value,
                        "urgency": nudge.urgency,
                    },
                    status=NotificationStatus.QUEUED,
                    created_at=now,
                )
                uow.notifications.add(notif)

                events.publish(
                    ChannelMessageQueued(
                        message_id=notif.id,
                        channel_type=notif.channel.value,
                        recipient_phone=nudge.recipient_phone,
                        template_name=notif.template_name,
                        template_params=notif.template_params,
                    )
                )

                audit.record(
                    AuditEvent(
                        tenant_id=tenant_id,
                        actor_id=SYSTEM_WORKER_ACTOR_ID,
                        actor_type=SYSTEM_WORKER_ACTOR_TYPE,
                        action=AuditAction.CREATE.value,
                        resource_type="NOTIFICATION",
                        resource_id=str(notif.id),
                        outcome="SUCCESS",
                        provenance_metadata={
                            "trigger": "scheduler_caregiver_nudge",
                            "milestone": nudge.milestone.value,
                            "patient_id": str(patient.id),
                        },
                    )
                )
                scheduled_count += 1

            if scheduled_count > 0:
                uow.commit()
            return scheduled_count
        finally:
            uow.close()

