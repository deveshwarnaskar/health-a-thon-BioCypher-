"""AddCareTeamMember command (Gate 10H-B).

Administrator provisioning of a care-team membership (clinician record) bound
to an authenticated platform user within the authenticated tenant. The role
vocabulary is the frozen Phase 1 set; user_id is never accepted as tenant.
"""

from dataclasses import dataclass
from uuid import UUID

from ...domain.entities import CareTeamRole


@dataclass(frozen=True)
class AddCareTeamMember:
    user_id: UUID
    role: CareTeamRole
    display_name: str
    facility_id: UUID
    correlation_id: UUID | None = None