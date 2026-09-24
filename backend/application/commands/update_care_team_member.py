"""UpdateCareTeamMember command contract (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID

from backend.domain.entities.care_team_member import CareTeamRole


@dataclass(frozen=True)
class UpdateCareTeamMember:
    member_id: UUID
    role: CareTeamRole | None = None
    display_name: str | None = None
    facility_id: UUID | None = None
    active: bool | None = None
    correlation_id: UUID | None = None
