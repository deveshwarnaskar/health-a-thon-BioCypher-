"""GetFacility use case (Gate 10K-B)."""

from backend.application.dtos.admin import FacilityResult
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries.get_facility import GetFacility


class GetFacilityHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, query: GetFacility) -> FacilityResult:
        facility = self._uow.facilities.get(query.facility_id)
        return FacilityResult(
            facility_id=facility.id,
            tenant_id=facility.tenant_id,
            name=facility.name,
            active=facility.active,
            created_at=facility.created_at,
        )
