"""ListCareTeamMembers use case (Gate 10K-B)."""

from backend.application.dtos.admin import CareTeamMemberListResult, CareTeamMemberResult
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries.list_care_team_members import ListCareTeamMembers


class ListCareTeamMembersHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, query: ListCareTeamMembers) -> CareTeamMemberListResult:
        all_members = self._uow.care_team_members.list()
        filtered = []
        for m in all_members:
            if query.facility_id is not None and m.facility_id != query.facility_id:
                continue
            if query.role is not None and m.role.value != query.role:
                continue
            filtered.append(m)

        items = [
            CareTeamMemberResult(
                member_id=m.id,
                user_id=m.user_id,
                role=m.role.value,
                display_name=m.display_name,
                facility_id=m.facility_id,
                active=m.active,
            )
            for m in filtered[: query.limit]
        ]
        return CareTeamMemberListResult(items=items, total=len(filtered))
