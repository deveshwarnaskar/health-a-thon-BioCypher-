"""DeactivateFacility command contract (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeactivateFacility:
    facility_id: UUID
    correlation_id: UUID | None = None
