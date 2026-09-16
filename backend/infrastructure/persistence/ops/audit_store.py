"""SqlAlchemyAuditStore (Gate 09 §10/§11).

Relational implementation of the immutable ``AuditStore`` port. Only
``record`` and ``query`` — no update/delete/truncate paths exist in code, and
the database layer additionally revokes those privileges and installs a guard
trigger (migration 0003) so even direct SQL cannot mutate audit history.

The store is tenant-scoped: it carries the bound ``tenant_id`` so a session can
never fund audit rows for a different tenant.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.application.ops.contracts import AuditEvent
from ..models.ops_models import AuditEventModel


def _model_to_event(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        audit_event_id=model.audit_event_id,
        tenant_id=model.tenant_id,
        actor_id=model.actor_id,
        actor_type=model.actor_type,
        action=model.action,
        resource_type=model.resource_type,
        resource_id=model.resource_id,
        occurred_at=model.occurred_at,
        correlation_id=model.correlation_id or "",
        request_id=model.request_id or "",
        source_ip=model.source_ip,
        outcome=model.outcome,
        reason=model.reason,
        provenance_metadata=dict(model.provenance_metadata or {}),
    )


class SqlAlchemyAuditStore:
    """SQLAlchemy-backed append-only audit store (tenant-scoped)."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyAuditStore")
        self.session = session
        self.tenant_id = tenant_id

    def record(self, event: AuditEvent) -> None:
        self.session.add(
            AuditEventModel(
                audit_event_id=event.audit_event_id,
                tenant_id=self.tenant_id,
                actor_id=(
                    event.actor_id
                    if event.actor_id is not None
                    else UUID("00000000-0000-0000-0000-000000000001")
                ),
                actor_type=event.actor_type,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id or None,
                request_id=event.request_id or None,
                source_ip=event.source_ip,
                outcome=event.outcome,
                reason=event.reason,
                provenance_metadata=dict(event.provenance_metadata or {}),
            )
        )

    def query(
        self,
        *,
        limit: int = 50,
        actor_id: UUID | None = None,
        action: str | None = None,
    ) -> list[AuditEvent]:
        stmt = select(AuditEventModel).where(AuditEventModel.tenant_id == self.tenant_id)
        if actor_id is not None:
            stmt = stmt.where(AuditEventModel.actor_id == actor_id)
        if action is not None:
            stmt = stmt.where(AuditEventModel.action == action)
        stmt = stmt.order_by(AuditEventModel.occurred_at.desc()).limit(limit)
        return [_model_to_event(m) for m in self.session.scalars(stmt).all()]


__all__ = ["SqlAlchemyAuditStore"]