"""GetMedicationPlan query handler (Gate 10F-B).

Resolves ONE clinician-authored medication plan. The patient must exist, be
active, and belong to the authenticated member's facility; otherwise the plan
is treated as not found so cross-facility/deactivated reads never leak
existence.
"""

from __future__ import annotations

from ..dtos.clinician_reads import MedicationPlanRecord
from ..ports.unit_of_work import UnitOfWork
from ..queries import GetMedicationPlan
from ...domain.exceptions import EntityNotFound


class GetMedicationPlanHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, q: GetMedicationPlan) -> MedicationPlanRecord:
        plan = self._uow.medication_plans.get(q.plan_id)
        patient = self._uow.patients.get(plan.patient_id)
        if not getattr(patient, "active", True):
            raise EntityNotFound(f"medication_plan {q.plan_id} not found")
        if patient.facility_id != q.facility_id:
            raise EntityNotFound(f"medication_plan {q.plan_id} not found")
        return MedicationPlanRecord(
            medication_plan_id=plan.id,
            patient_id=plan.patient_id,
            medication=plan.medication,
            instruction=plan.instruction,
            active=plan.active,
            prescribed_by_role=plan.prescribed_by_role.value,
            created_at=plan.created_at,
        )