"""Transactional outbox publisher implementation (Gate 05).

Persists canonical domain events to the outbox table within the same database transaction.
Guarantees zero event loss across state changes.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session

from backend.domain.events.base import DomainEvent
from ..models.outbox_models import DomainEventOutboxModel


def _serialize_value(val: object) -> object:
    if isinstance(val, (UUID, datetime)):
        return str(val)
    if isinstance(val, dict):
        return {str(k): _serialize_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [_serialize_value(v) for v in val]
    return val


class SqlAlchemyOutboxDomainEventPublisher:
    """Outbox-backed DomainEventPublisher implementation."""

    def __init__(self, session: Session, tenant_id: UUID | None = None) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def publish(self, event: DomainEvent) -> None:
        if not is_dataclass(event):
            raw_payload = {"event_type": event.event_type}
        else:
            raw_payload = asdict(event)

        payload = {k: _serialize_value(v) for k, v in raw_payload.items()}

        outbox_entry = DomainEventOutboxModel(
            event_id=event.event_id,
            tenant_id=self.tenant_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            patient_id=event.patient_id,
            correlation_id=event.correlation_id,
            payload=payload,
            published_at=None,
        )
        self.session.add(outbox_entry)
