"""ListPatients query handler (Gate 10F-B).

Returns the clinician's active patient cohort restricted to the authenticated
member's facility:

    patient.tenant_id == ctx.tenant_id       (repository + RLS)
    AND patient.facility_id == facility_id   (handler)
    AND patient.active == true               (handler)
"""

from __future__ import annotations

from ..dtos.clinician_reads import PatientList, PatientRecord
from ..ports.unit_of_work import UnitOfWork
from ..queries import ListPatients


class ListPatientsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, q: ListPatients) -> PatientList:
        patients = self._uow.patients.list()
        items = [
            PatientRecord(
                patient_id=p.id,
                uh_id=p.uh_id.value,
                name=p.name,
                facility_id=p.facility_id,
                active=p.active,
                created_at=p.created_at,
            )
            for p in patients
            if getattr(p, "active", True) and p.facility_id == q.facility_id
        ]
        items.sort(key=lambda r: (r.created_at, r.patient_id))
        items = items[: q.limit]
        return PatientList(patient_count=len(items), items=items)