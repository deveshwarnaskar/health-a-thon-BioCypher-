"""GetCareTeamMember use case (Gate 10K-B)."""

from backend.application.dtos.admin import CareTeamMemberResult
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries.get_care_team_member import GetCareTeamMember


class GetCareTeamMemberHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, query: GetCareTeamMember) -> CareTeamMemberResult:
        member = self._uow.care_team_members.get_by_id(query.member_id)
        return CareTeamMemberResult(
            member_id=member.id,
            user_id=member.user_id,
            role=member.role.value,
            display_name=member.display_name,
            facility_id=member.facility_id,
            active=member.active,
        )
