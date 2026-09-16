"""SqlAlchemyIdempotencyStore (Gate 09 §7).

Relational implementation of the ``IdempotencyStore`` port. The unique
constraint (tenant_id, actor_id, idempotency_key) is the concurrency guard:
the first request to insert the reservation wins; every other request observes
the winner's state (in-progress → 409, completed → replay, mismatched
fingerprint → 409). Expired reservations are recycled so a client key is
reusable after the TTL window.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.application.ops.contracts import ReservationResult
from ..models.ops_models import IdempotencyRecordModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class SqlAlchemyIdempotencyStore:
    """SQLAlchemy-backed idempotency reservation store."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- port ------------------------------------------------------------

    def reserve(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        key: str,
        fingerprint: str,
        ttl_seconds: int = 86_400,
    ) -> ReservationResult:
        now = _utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds)

        inserted = self._insert_or_nothing(tenant_id, actor_id, key, fingerprint, now, expires_at)
        if inserted:
            return ReservationResult(accepted=True)

        row = self._existing(tenant_id, actor_id, key)
        if row is None:
            # Lost insert race: treat the scoped key as unavailable; the
            # in-progress holder will resolve shortly.
            return ReservationResult(accepted=False, conflict="in_progress")

        if _aware(row.expires_at) is not None and _aware(row.expires_at) <= now:
            # Expired reservation → recycle the scoped key.
            row.request_fingerprint = fingerprint
            row.status = "in_progress"
            row.status_code = None
            row.response_headers = None
            row.response_body = None
            row.created_at = now
            row.expires_at = expires_at
            return ReservationResult(accepted=True)

        if row.status == "completed":
            if row.request_fingerprint == fingerprint:
                return ReservationResult(
                    accepted=False,
                    replay=True,
                    status_code=row.status_code,
                    headers=dict(row.response_headers or {}),
                    body=row.response_body or "",
                )
            return ReservationResult(accepted=False, conflict="mismatch")

        if row.request_fingerprint == fingerprint:
            return ReservationResult(accepted=False, conflict="in_progress")
        return ReservationResult(accepted=False, conflict="mismatch")

    def complete(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        key: str,
        status_code: int,
        headers: dict[str, str],
        body: str,
    ) -> None:
        row = self._existing(tenant_id, actor_id, key)
        if row is None:
            return
        row.status = "completed"
        row.status_code = status_code
        row.response_headers = headers
        row.response_body = body

    def release_failed(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        key: str,
    ) -> None:
        row = self._existing(tenant_id, actor_id, key)
        if row is not None:
            self.session.delete(row)

    # -- internals -------------------------------------------------------

    def _insert_or_nothing(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        key: str,
        fingerprint: str,
        now: datetime,
        expires_at: datetime,
    ) -> bool:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        values = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "idempotency_key": key,
            "request_fingerprint": fingerprint,
            "status": "in_progress",
            "created_at": now,
            "expires_at": expires_at,
        }
        dialect = self.session.get_bind().dialect.name
        insert = pg_insert(IdempotencyRecordModel) if dialect == "postgresql" else sqlite_insert(IdempotencyRecordModel)
        stmt = insert.values(**values).on_conflict_do_nothing(
            index_elements=["tenant_id", "actor_id", "idempotency_key"]
        ).returning(IdempotencyRecordModel.id)
        return self.session.execute(stmt).first() is not None

    def _existing(
        self, tenant_id: UUID, actor_id: UUID, key: str
    ) -> IdempotencyRecordModel | None:
        stmt = select(IdempotencyRecordModel).where(
            IdempotencyRecordModel.tenant_id == tenant_id,
            IdempotencyRecordModel.actor_id == actor_id,
            IdempotencyRecordModel.idempotency_key == key,
        )
        return self.session.scalars(stmt).first()


__all__ = ["SqlAlchemyIdempotencyStore"]