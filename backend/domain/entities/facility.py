"""Facility entity (Gate 10K-B).

Clinical facility belonging to an organizational tenant.
Carries operational status (active/inactive) and facility identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class Facility:
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID = field(default_factory=uuid4)
    name: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def deactivate(self) -> None:
        self.active = False

    def activate(self) -> None:
        self.active = True

    def rename(self, new_name: str) -> None:
        cleaned = new_name.strip()
        if not cleaned:
            raise ValueError("Facility name cannot be empty")
        self.name = cleaned
