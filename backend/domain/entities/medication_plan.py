"""MedicationPlan entity (Gate 03).

CRITICAL authority rule: MedicationPlan is CLINICIAN-AUTHORED ONLY.

- Clinician instructions: created/updated/deactivated only by licensed clinical
  roles (``CareTeamRole.can_author_medication``).
- Patient administration/adherence observations and AI-generated observations
  can never create, titrate, modify, or activate a plan.

This is an explicit domain invariant, not a UI convention, and it is enforced
at construction and on every mutation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from ..exceptions import UnauthorizedMedicationPlanMutation
from .care_team_member import CareTeamRole


@dataclass
class MedicationPlan:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    prescribed_by_user_id: UUID = field(default_factory=uuid4)
    prescribed_by_role: CareTeamRole = CareTeamRole.DOCTOR
    medication: str = ""
    instruction: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.prescribed_by_role.can_author_medication:
            raise UnauthorizedMedicationPlanMutation(
                f"role {self.prescribed_by_role.value} cannot author a MedicationPlan; "
                "only licensed clinicians (doctor/nurse/dietitian) may prescribe"
            )

    def _require_clinician(self, actor: CareTeamRole) -> None:
        if not actor.can_author_medication:
            raise UnauthorizedMedicationPlanMutation(
                f"{actor.value} attempted to modify a MedicationPlan; "
                "plans are clinician-authored only and AI/patients are barred"
            )

    def update_instruction(self, actor: CareTeamRole, new_instruction: str) -> None:
        self._require_clinician(actor)
        self.instruction = new_instruction

    def deactivate(self, actor: CareTeamRole) -> None:
        self._require_clinician(actor)
        self.active = False

    def reactivate(self, actor: CareTeamRole) -> None:
        self._require_clinician(actor)
        self.active = True