"""DeactivateCareTeamMember command contract (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeactivateCareTeamMember:
    member_id: UUID
    correlation_id: UUID | None = None
