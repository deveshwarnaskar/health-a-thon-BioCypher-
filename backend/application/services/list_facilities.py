"""ListFacilities use case (Gate 10K-B)."""

from backend.application.dtos.admin import FacilityListResult, FacilityResult
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries.list_facilities import ListFacilities


class ListFacilitiesHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, query: ListFacilities) -> FacilityListResult:
        all_facilities = self._uow.facilities.list()
        items = [
            FacilityResult(
                facility_id=f.id,
                tenant_id=f.tenant_id,
                name=f.name,
                active=f.active,
                created_at=f.created_at,
            )
            for f in all_facilities[: query.limit]
        ]
        return FacilityListResult(items=items, total=len(all_facilities))
