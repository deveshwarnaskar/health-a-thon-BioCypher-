"""ListCareTeamMembers query contract (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListCareTeamMembers:
    facility_id: UUID | None = None
    role: str | None = None
    limit: int = 50
