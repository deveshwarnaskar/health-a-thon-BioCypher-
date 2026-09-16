"""SqlAlchemyOutboxWorkerStore (Gate 09 §13/§16).

Transactional-outbox claim/mark for the application-layer ``OutboxWorker``.

Claiming (PostgreSQL):
    SELECT ... FOR UPDATE SKIP LOCKED ORDER BY occurred_at LIMIT 10
    → mark each row PROCESSING (locked_by/locked_at) → COMMIT immediately so
    the lease is durable and other workers can race for different rows.

Reclaiming:
    PROCESSING rows whose locked_at is older than the lease window are treated
    as due (a crashed worker's lease has expired).

Marking is idempotent per event_id and applies the exact state transition the
worker already decided (PUBLISHED / retry / DEAD_LETTER).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from backend.application.ops.contracts import (
    DeliveryOutcome,
    OutboxJob,
)
from ..models.outbox_models import DomainEventOutboxModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _model_to_job(model: DomainEventOutboxModel) -> OutboxJob:
    return OutboxJob(
        event_id=model.event_id,
        event_type=model.event_type,
        tenant_id=model.tenant_id,
        patient_id=model.patient_id,
        correlation_id=model.correlation_id,
        payload=dict(model.payload or {}),
        occurred_at=model.occurred_at,
        retry_count=model.retry_count,
        locked_by=model.locked_by,
        locked_at=model.locked_at,
    )


class SqlAlchemyOutboxWorkerStore:
    """SQLAlchemy-backed transactional-outbox worker store."""

    def __init__(
        self,
        session_factory_or_session: sessionmaker[Session] | Session,
    ) -> None:
        if isinstance(session_factory_or_session, Session):
            self.session_factory: Callable[[], Session] = lambda: session_factory_or_session
        else:
            self.session_factory = session_factory_or_session

    def claim(self, limit: int, worker_id: str, lease_seconds: int) -> list[OutboxJob]:
        session = self.session_factory()
        try:
            now = _utcnow()
            cutoff = now - timedelta(seconds=lease_seconds)

            stmt = select(DomainEventOutboxModel).where(
                or_(
                    and_(
                        DomainEventOutboxModel.status == "pending",
                        or_(
                            DomainEventOutboxModel.next_attempt_at.is_(None),
                            DomainEventOutboxModel.next_attempt_at <= now,
                        ),
                    ),
                    and_(
                        DomainEventOutboxModel.status == "processing",
                        DomainEventOutboxModel.locked_at.is_not(None),
                        DomainEventOutboxModel.locked_at <= cutoff,
                    ),
                )
            ).order_by(DomainEventOutboxModel.occurred_at.asc()).limit(limit)

            if session.get_bind().dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)

            rows = list(session.scalars(stmt).all())
            for row in rows:
                row.status = "processing"
                row.locked_by = worker_id
                row.locked_at = now
            session.commit()
            return [_model_to_job(row) for row in rows]
        finally:
            session.close()

    def mark(
        self,
        event_id: UUID,
        outcome: DeliveryOutcome,
        *,
        error: str | None = None,
        next_attempt_at=None,
    ) -> None:
        session = self.session_factory()
        try:
            row = session.get(DomainEventOutboxModel, event_id)
            if row is None:
                return
            now = _utcnow()
            row.locked_by = None
            row.locked_at = None

            if outcome is DeliveryOutcome.SUCCESS:
                row.status = "published"
                row.published_at = now
                row.next_attempt_at = None
                row.last_error = None
            elif outcome is DeliveryOutcome.PERMANENT:
                row.status = "dead_letter"
                row.next_attempt_at = None
                row.last_error = error
            else:  # RETRYABLE
                row.status = "pending"
                row.retry_count = row.retry_count + 1 if row.retry_count is not None else 1
                row.next_attempt_at = next_attempt_at
                row.last_error = error
            session.commit()
        finally:
            session.close()


__all__ = ["SqlAlchemyOutboxWorkerStore"]