"""AdminListPatients use case (Gate 10K-B).

Admin-scoped, PHI-minimized operational patient directory query.
"""

from backend.application.dtos.admin import AdminPatientListResult, AdminPatientSummaryResult
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries.admin_list_patients import AdminListPatients


class AdminListPatientsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, query: AdminListPatients) -> AdminPatientListResult:
        all_patients = self._uow.patients.list()
        filtered = []
        for p in all_patients:
            if query.facility_id is not None and p.facility_id != query.facility_id:
                continue
            if query.active is not None and p.active != query.active:
                continue
            filtered.append(p)

        items = []
        for p in filtered[: query.limit]:
            mapping = self._uow.identity_mappings.get_by_patient_id(p.id)
            has_active = bool(mapping and mapping.active)
            items.append(
                AdminPatientSummaryResult(
                    patient_id=p.id,
                    uh_id=p.uh_id.value,
                    name=p.name,
                    facility_id=p.facility_id,
                    phone=p.phone.value if p.phone else None,
                    active=p.active,
                    has_active_mapping=has_active,
                    created_at=p.created_at,
                )
            )
        return AdminPatientListResult(items=items, total=len(filtered))
