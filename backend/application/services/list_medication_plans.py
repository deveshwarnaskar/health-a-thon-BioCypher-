"""ListMedicationPlans query handler (Gate 10F-B).

Returns clinician-authored medication plans restricted to the authenticated
member's facility:

    plan.tenant_id == ctx.tenant_id             (repository + RLS)
    AND patient.facility_id == facility_id      (handler)
    AND patient.active == true                  (handler)

Medication plans are clinician-authored-only domain aggregates; proxy roles are
denied at the HTTP authorization boundary before this handler ever runs.
"""

from __future__ import annotations

from ..dtos.clinician_reads import MedicationPlanList, MedicationPlanRecord
from ..ports.unit_of_work import UnitOfWork
from ..queries import ListMedicationPlans
from ...domain.exceptions import EntityNotFound


class ListMedicationPlansHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, q: ListMedicationPlans) -> MedicationPlanList:
        plans = self._uow.medication_plans.list()
        items = [
            record
            for record in (self._maybe_record(q, p) for p in plans)
            if record is not None
        ]
        items.sort(key=lambda r: (r.created_at, r.medication_plan_id))
        items = items[: q.limit]
        return MedicationPlanList(plan_count=len(items), items=items)

    def _maybe_record(self, q: ListMedicationPlans, plan) -> MedicationPlanRecord | None:
        try:
            patient = self._uow.patients.get(plan.patient_id)
        except EntityNotFound:
            return None
        if not getattr(patient, "active", True):
            return None
        if patient.facility_id != q.facility_id:
            return None
        return MedicationPlanRecord(
            medication_plan_id=plan.id,
            patient_id=plan.patient_id,
            medication=plan.medication,
            instruction=plan.instruction,
            active=plan.active,
            prescribed_by_role=plan.prescribed_by_role.value,
            created_at=plan.created_at,
        )