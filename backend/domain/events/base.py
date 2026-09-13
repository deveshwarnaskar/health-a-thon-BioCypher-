"""Canonical domain event base abstraction (Gate 02B placeholder).

A unified append-only event model (``clinical_events``) is agreed for the
target architecture. This base reserves the common envelope; no concrete
events are implemented yet.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    patient_profile_id: UUID | None = None