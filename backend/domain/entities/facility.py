"""Facility entity placeholder (Gate 02B)."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Facility:
    id: UUID
    organization_id: UUID
    name: str
    created_at: datetime = field(default_factory=datetime.utcnow)