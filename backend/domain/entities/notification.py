"""Notification entity (Gate 10L).

Assistive outbound notification with explicit tenant scoping and deterministic lifecycle.
Carries ONLY authorized communication templates and parameters — zero uncontrolled
or raw clinical analytics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from ..exceptions import DomainError, InvalidStateTransition


class NotificationStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationChannel(str, Enum):
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    IN_APP = "IN_APP"


class NotificationType(str, Enum):
    REMINDER = "reminder"
    ALERT = "alert"
    TASK_ASSIGNED = "task_assigned"
    CARE_UPDATE = "care_update"
    CLINICAL_COMMUNICATION = "clinical_communication"
    WELCOME = "welcome"


_TRANSITIONS: dict[NotificationStatus, set[NotificationStatus]] = {
    NotificationStatus.PENDING: {NotificationStatus.QUEUED, NotificationStatus.CANCELLED},
    NotificationStatus.QUEUED: {
        NotificationStatus.DELIVERING,
        NotificationStatus.DELIVERED,
        NotificationStatus.FAILED,
        NotificationStatus.CANCELLED,
    },
    NotificationStatus.DELIVERING: {
        NotificationStatus.DELIVERED,
        NotificationStatus.FAILED,
        NotificationStatus.QUEUED,  # for retryable backoff
    },
    NotificationStatus.DELIVERED: set(),
    NotificationStatus.FAILED: set(),
    NotificationStatus.CANCELLED: set(),
}

FORBIDDEN_NOTIFICATION_FIELDS = frozenset({
    "carbs_grams",
    "glycemic_index",
    "clinical_notes",
    "ai_review",
    "ai_diagnosis",
    "risk_score",
})


@dataclass
class Notification:
    """Canonical notification domain entity."""

    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID = field(default_factory=uuid4)
    recipient_id: UUID = field(default_factory=uuid4)
    recipient_phone: str = ""
    patient_id: UUID | None = None
    notification_type: NotificationType = NotificationType.REMINDER
    channel: NotificationChannel = NotificationChannel.WHATSAPP
    template_name: str = "general_notification"
    template_params: dict[str, str] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    failure_reason: str | None = None
    correlation_id: UUID | None = None
    retry_count: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            self.status = NotificationStatus(self.status)
        if isinstance(self.channel, str):
            self.channel = NotificationChannel(self.channel)
        if isinstance(self.notification_type, str):
            self.notification_type = NotificationType(self.notification_type)

        # Enforce clinical information asymmetry boundary: no hidden clinical analytics
        for key in (self.template_params or {}):
            if key.lower() in FORBIDDEN_NOTIFICATION_FIELDS:
                raise DomainError(
                    f"Forbidden clinical field '{key}' detected in notification parameters"
                )

    def _transition(self, target: NotificationStatus) -> None:
        allowed = _TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidStateTransition(
                f"notification cannot move {self.status.value} -> {target.value}"
            )
        self.status = target

    def queue(self) -> None:
        self._transition(NotificationStatus.QUEUED)

    def mark_delivering(self) -> None:
        self._transition(NotificationStatus.DELIVERING)

    def mark_delivered(self, delivered_at: datetime | None = None) -> None:
        self._transition(NotificationStatus.DELIVERED)
        self.delivered_at = delivered_at or datetime.now(timezone.utc)

    def mark_failed(self, reason: str, failed_at: datetime | None = None) -> None:
        self._transition(NotificationStatus.FAILED)
        self.failed_at = failed_at or datetime.now(timezone.utc)
        self.failure_reason = reason

    def requeue_for_retry(self) -> None:
        self._transition(NotificationStatus.QUEUED)
        self.retry_count += 1

    def cancel(self) -> None:
        self._transition(NotificationStatus.CANCELLED)
