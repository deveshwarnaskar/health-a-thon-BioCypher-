"""CareTeamMember / clinician entity (Gate 03).

Role vocabulary is frozen by Phase 1 universal mobile: Doctor, Nurse, Care
Coordinator, Dietitian/Diabetes Educator, Field Health Worker. Only licensed
clinical roles may author medication plans.
"""

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4


class CareTeamRole(str, Enum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    CARE_COORDINATOR = "care_coordinator"
    DIETITIAN = "dietitian"
    FIELD_HEALTH_WORKER = "field_health_worker"

    @property
    def can_author_medication(self) -> bool:
        return self in {CareTeamRole.DOCTOR, CareTeamRole.NURSE, CareTeamRole.DIETITIAN}


@dataclass
class CareTeamMember:
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    role: CareTeamRole = CareTeamRole.DOCTOR
    display_name: str = ""
    facility_id: UUID | None = None
    active: bool = True

    def deactivate(self) -> None:
        self.active = False