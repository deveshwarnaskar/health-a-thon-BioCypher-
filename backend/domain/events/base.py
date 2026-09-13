"""Canonical domain event base abstraction (Gate 03).

Domain events are the vocabulary of "something happened" in the clinical
domain. They remain distinct from:

1. entity current state,
2. audit events,
3. system/observability telemetry,
4. channel (webhook) telemetry.

No event store, persistence, or TimescaleDB is introduced in this gate.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from ..exceptions import DomainValidationError


@dataclass(frozen=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    patient_id: UUID | None = None
    correlation_id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise DomainValidationError("domain event requires a non-empty event_type")