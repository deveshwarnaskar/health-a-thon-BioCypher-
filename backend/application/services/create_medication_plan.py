"""CreateMedicationPlan use case (Gate 04).

CLINICIAN-AUTHORED ONLY (frozen authority model). The handler resolves the
acting clinician's role from the authoritative ``CareTeamMember`` record.
The domain ``MedicationPlan`` construction enforces
``CareTeamRole.can_author_medication``; a non-clinician actor raises
``UnauthorizedMedicationPlanMutation`` and the transaction rolls back.

No AI, patient, caregiver, or automated model may reach this use case to
create a plan.
"""

from ..commands import CreateMedicationPlan
from ..dtos.results import MedicationPlanCreated
from ..ports.clock import Clock
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import MedicationPlan
from ._transaction import in_transaction


class CreateMedicationPlanHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._id_gen = id_gen

    def handle(self, cmd: CreateMedicationPlan) -> MedicationPlanCreated:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: CreateMedicationPlan) -> MedicationPlanCreated:
        member = self._uow.care_team_members.get(cmd.prescribed_by_user_id)
        plan = MedicationPlan(
            id=self._id_gen.new_uuid(),
            patient_id=cmd.patient_id,
            prescribed_by_user_id=member.id,
            prescribed_by_role=member.role,
            medication=cmd.medication,
            instruction=cmd.instruction,
            created_at=self._clock.now(),
        )
        self._uow.medication_plans.add(plan)
        return MedicationPlanCreated(
            medication_plan_id=plan.id,
            patient_id=cmd.patient_id,
        )