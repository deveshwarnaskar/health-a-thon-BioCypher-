"""CareTeamMembership entity placeholder (Gate 02B).

Binds a user to a patient profile with an RBAC care-team role.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CareTeamMembership:
    id: UUID
    patient_profile_id: UUID
    user_id: UUID
    role: str
    created_at: datetime = field(default_factory=datetime.utcnow)