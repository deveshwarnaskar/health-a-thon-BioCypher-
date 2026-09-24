"""GetPatient query handler (Gate 10F-B).

Resolves ONE active patient record within the authenticated member's facility.
Cross-facility, deactivated, or absent patients raise EntityNotFound so no
existence is leaked.
"""

from __future__ import annotations

from ..dtos.clinician_reads import PatientRecord
from ..ports.unit_of_work import UnitOfWork
from ..queries import GetPatient
from ...domain.exceptions import EntityNotFound


class GetPatientHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, q: GetPatient) -> PatientRecord:
        patient = self._uow.patients.get(q.patient_id)
        if not getattr(patient, "active", True):
            raise EntityNotFound(f"patient {q.patient_id} not found")
        if patient.facility_id != q.facility_id:
            raise EntityNotFound(f"patient {q.patient_id} not found")
        return PatientRecord(
            patient_id=patient.id,
            uh_id=patient.uh_id.value,
            name=patient.name,
            facility_id=patient.facility_id,
            active=patient.active,
            created_at=patient.created_at,
        )