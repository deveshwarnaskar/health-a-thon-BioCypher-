"""AdminGetPatient use case (Gate 10K-B).

Admin-scoped, PHI-minimized single patient inspection query.
"""

from backend.application.dtos.admin import AdminPatientSummaryResult
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries.admin_get_patient import AdminGetPatient


class AdminGetPatientHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, query: AdminGetPatient) -> AdminPatientSummaryResult:
        patient = self._uow.patients.get(query.patient_id)
        mapping = self._uow.identity_mappings.get_by_patient_id(patient.id)
        has_active = bool(mapping and mapping.active)
        return AdminPatientSummaryResult(
            patient_id=patient.id,
            uh_id=patient.uh_id.value,
            name=patient.name,
            facility_id=patient.facility_id,
            phone=patient.phone.value if patient.phone else None,
            active=patient.active,
            has_active_mapping=has_active,
            created_at=patient.created_at,
        )
