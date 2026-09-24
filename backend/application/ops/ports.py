"""Gate 09 — Outbound ports (protocols).

Every concrete infrastructure implementation (relational stores, counter
stores, rate limiters, channel senders, resolvers) conforms to one of these
protocols so the application layer stays infrastructure-free.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable
from uuid import UUID

from backend.domain.entities import Patient

from .contracts import (
    AuditEvent,
    DeliveryOutcome,
    DeliveryResult,
    OutboundMessage,
    OutboxJob,
    RateLimitFailurePolicy,
    RateLimitResult,
    ResolvedChannelPatient,
    ReservationResult,
    WebhookReceipt,
)


@runtime_checkable
class IdempotencyStore(Protocol):
    """Client-driven idempotency reservation lifecycle (Gate 09 §7.2)."""

    def reserve(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        key: str,
        fingerprint: str,
        ttl_seconds: int = 86_400,
    ) -> ReservationResult: ...

    def complete(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        key: str,
        status_code: int,
        headers: dict[str, str],
        body: str,
    ) -> None: ...

    def release_failed(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        key: str,
    ) -> None: ...


@runtime_checkable
class WebhookReceiptStore(Protocol):
    """Provider delivery deduplication (Gate 09 §8).

    ``record`` returns ``True`` when the delivery is fresh (caller should
    proceed and acknowledge), or ``False`` when it is a duplicate within the
    retention window (caller acknowledges and drops the payload).
    """

    def record(self, receipt: WebhookReceipt) -> bool: ...


@runtime_checkable
class AuditStore(Protocol):
    """Append-only audit port (Gate 09 §11.1.3).

    Only ``record`` and ``query`` exist. There are deliberately NO update or
    delete methods: immutability is additionally enforced at the database
    layer (permissions + trigger).
    """

    def record(self, event: AuditEvent) -> None: ...

    def query(
        self,
        *,
        limit: int = 50,
        actor_id: UUID | None = None,
        action: str | None = None,
    ) -> list[AuditEvent]: ...


@runtime_checkable
class RateLimiter(Protocol):
    """Sliding-window rate limiter (Gate 09 §9.1)."""

    def check_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        burst_allowance: int = 0,
        failure_policy: RateLimitFailurePolicy = RateLimitFailurePolicy.DEGRADE,
    ) -> RateLimitResult: ...


@runtime_checkable
class ChannelSender(Protocol):
    """Provider-neutral outbound messaging (Gate 09 §14.1)."""

    def send(self, message: OutboundMessage) -> DeliveryResult: ...


@runtime_checkable
class ChannelTenantResolver(Protocol):
    """Resolve a channel sender phone to a (tenant, patient) anchor.

    Returns only identifiers, never clinical data. Backed by a narrow,
    privileged routing lookup; the caller must re-resolve the patient inside
    the tenant's postgres RLS scope before touching any domain state.
    """

    def resolve(self, phone: str) -> ResolvedChannelPatient | None: ...


@runtime_checkable
class OutboxWorkerStore(Protocol):
    """Transactional outbox claiming/marking (Gate 09 §13)."""

    def claim(self, limit: int, worker_id: str, lease_seconds: int) -> list[OutboxJob]: ...

    def mark(
        self,
        event_id: UUID,
        outcome: DeliveryOutcome,
        *,
        error: str | None = None,
        next_attempt_at=None,
    ) -> None: ...


# Factory callables wired by infrastructure.
UowFactory = Callable[[UUID], object]
PublisherFactory = Callable[[object], object]
AuditFactory = Callable[[object], AuditStore]


@runtime_checkable
class ChannelPatientResolver(Protocol):
    """Resolve a patient within an already-bound tenant scope."""

    def resolve(self, tenant_id: UUID, phone: str) -> Patient | None: ...


@runtime_checkable
class WorkerTelemetryPort(Protocol):
    """Observability port for worker job execution lifecycle (Gate 10P-D)."""

    def on_worker_health(self, is_healthy: bool) -> None: ...

    def on_sync_activity(self, outcome: str) -> None: ...

    def on_job_started(self, event_type: str, correlation_id: str) -> object: ...

    def on_job_finished(
        self,
        event_type: str,
        outcome: str,
        duration_sec: float,
        failure_type: str | None = None,
        context: object = None,
    ) -> None: ...