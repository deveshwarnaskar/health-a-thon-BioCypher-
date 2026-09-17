"""GetFacility query contract (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetFacility:
    facility_id: UUID
