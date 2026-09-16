"""Gate 09 — Operational contracts (value objects, enums, constants).

All Gate 09 operational data shapes live outside the clinical domain and carry
no PHI by construction:

- ``IdempotencyRecord``/``ReservationResult``  — client idempotency lifecycle
- ``WebhookReceipt``                            — provider delivery deduplication
- ``AuditEvent``                                — immutable compliance trail
- ``RateLimitResult``                           — sliding-window verdicts
- ``OutboundMessage``/``DeliveryResult``        — provider-neutral outbound send
- ``OutboxJob``                                 — one leased outbox work item

The system-worker identity is frozen here so every actor (HTTP or background)
has a well-defined audit identity.
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import UUID

# The frozen system-worker identity used by background jobs (Gate 09 §20).
SYSTEM_WORKER_ACTOR_ID = UUID("00000000-0000-0000-0000-000000000001")
SYSTEM_WORKER_ACTOR_TYPE = "SYSTEM_WORKER"

# Event types written to / consumed from the transactional outbox.
WEBHOOK_INTAKE_EVENT_TYPE = "whatsapp.message.received"
CHANNEL_SEND_EVENT_TYPE = "channel.message.send"

# Default webhook deduplication retention window (Gate 09 §8.3).
WEBHOOK_REPLAY_RETENTION_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Default idempotency record TTL (Gate 09 §7.5).
IDEMPOTENCY_TTL_SECONDS = 86_400  # 24 hours

# Transactional outbox worker policy (Gate 09 §13/§16).
OUTBOX_MAX_RETRIES = 5
OUTBOX_LEASE_SECONDS = 300  # re-lease a crashed worker's row after 5 minutes


class IdempotencyStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class IdempotencyRecord:
    """One scoped idempotency reservation (tenant ‖ actor ‖ key)."""

    tenant_id: UUID
    actor_id: UUID
    idempotency_key: str
    request_fingerprint: str
    status: IdempotencyStatus
    status_code: int | None = None
    response_headers: Mapping[str, str] | None = None
    response_body: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ReservationResult:
    """Outcome of ``IdempotencyStore.reserve``.

    - ``accepted=True``            → caller may execute the handler.
    - ``accepted=False, replay``   → caller returns the cached response.
    - ``accepted=False, conflict`` → ``in_progress`` (concurrent) or
      ``mismatch`` (same key, different fingerprint).
    """

    accepted: bool
    replay: bool = False
    conflict: str | None = None
    status_code: int | None = None
    headers: Mapping[str, str] | None = None
    body: str | None = None


@dataclass(frozen=True)
class WebhookReceipt:
    """Deduplication receipt for one verified provider delivery."""

    receipt_id: UUID
    provider: str
    provider_message_id: str
    event_type: str
    received_at: datetime
    source_phone: str = ""


class ActorType(str, Enum):
    CLINICIAN = "CLINICIAN"
    PATIENT = "PATIENT"
    CAREGIVER = "CAREGIVER"
    ADMIN = "ADMIN"
    SYSTEM_WORKER = SYSTEM_WORKER_ACTOR_TYPE


class AuditAction(str, Enum):
    LOGIN = "LOGIN"
    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    REVOKE = "REVOKE"
    REVIEW = "REVIEW"
    RECEIVE = "RECEIVE"
    SEND = "SEND"


class AuditOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILED = "FAILED"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class AuditEvent:
    """Immutable compliance record (Gate 09 §10.1).

    Deliberately PHI-minimal: no clinical values, drug doses, passwords,
    tokens, or raw channel payloads are permitted in any field.
    """

    audit_event_id: UUID = field(default_factory=_uuid.uuid4)
    tenant_id: UUID | None = None
    actor_id: UUID | None = None
    actor_type: str = SYSTEM_WORKER_ACTOR_TYPE
    action: str = AuditAction.READ.value
    resource_type: str = ""
    resource_id: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = ""
    request_id: str = ""
    source_ip: str | None = None
    outcome: str = AuditOutcome.SUCCESS.value
    reason: str | None = None
    provenance_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RateLimitResult:
    """Rate-limit verdict plus the standard response headers' values."""

    allowed: bool
    limit: int
    remaining: int
    reset_epoch: int
    retry_after_seconds: int = 0


class RateLimitFailurePolicy(str, Enum):
    """Behavior when the backing counter store is unavailable (Gate 09 §18)."""

    FAIL_CLOSED = "fail_closed"  # deny (429) — auth, AI, admin tiers
    FAIL_OPEN = "fail_open"  # allow — webhook tier
    DEGRADE = "degrade"  # fall back to in-process memory window


@dataclass(frozen=True)
class OutboundMessage:
    """Provider-neutral outbound notification (Gate 09 §14.1)."""

    message_id: UUID
    tenant_id: UUID
    recipient_phone: str
    channel_type: str
    template_name: str
    template_params: Mapping[str, str]
    correlation_id: str = ""

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], *, tenant_id: UUID) -> "OutboundMessage":
        """Rebuild from a transactional-outbox payload (sanitized, no PHI).

        The outbox row's ``tenant_id`` column (not the payload) carries the
        tenant binding; the caller supplies it explicitly.
        """
        return cls(
            message_id=UUID(str(payload["message_id"])),
            tenant_id=tenant_id,
            recipient_phone=str(payload["recipient_phone"]),
            channel_type=str(payload.get("channel_type") or "WHATSAPP"),
            template_name=str(payload.get("template_name") or "clinical_notification"),
            template_params={str(k): str(v) for k, v in (payload.get("template_params") or {}).items()},
            correlation_id=str(payload.get("correlation_id") or ""),
        )


@dataclass(frozen=True)
class DeliveryResult:
    """Result of an outbound provider call."""

    success: bool
    provider_delivery_id: str | None = None
    error_code: str | None = None
    retryable: bool = False


@dataclass(frozen=True)
class ResolvedChannelPatient:
    """Phone→patient routing decision: ONLY identifiers, never clinical data."""

    tenant_id: UUID
    patient_id: UUID


class OutboxStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    DEAD_LETTER = "dead_letter"


class DeliveryOutcome(str, Enum):
    SUCCESS = "success"
    RETRYABLE = "retryable"
    PERMANENT = "permanent"


@dataclass(frozen=True)
class OutboxJob:
    """One leased transactional-outbox work item."""

    event_id: UUID
    event_type: str
    tenant_id: UUID | None
    patient_id: UUID | None
    correlation_id: UUID | None
    payload: Mapping[str, Any]
    occurred_at: datetime
    retry_count: int
    locked_by: str | None = None
    locked_at: datetime | None = None


def utcnow() -> datetime:
    """Single time source for operational code (test-injectable via Clock where ports allow)."""
    return datetime.now(timezone.utc)