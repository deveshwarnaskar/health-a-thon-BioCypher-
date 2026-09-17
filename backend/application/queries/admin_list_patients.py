"""AdminListPatients query contract (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AdminListPatients:
    facility_id: UUID | None = None
    active: bool | None = None
    limit: int = 50
