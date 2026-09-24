"""UpdateFacility command contract (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UpdateFacility:
    facility_id: UUID
    name: str | None = None
    active: bool | None = None
    correlation_id: UUID | None = None
