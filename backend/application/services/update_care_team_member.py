"""UpdateCareTeamMember use case (Gate 10K-B)."""

from backend.application.commands.update_care_team_member import UpdateCareTeamMember
from backend.application.dtos.admin import CareTeamMemberResult
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services._transaction import in_transaction
from backend.domain.entities.care_team_member import CareTeamRole
from backend.domain.events.admin import CareTeamMemberUpdated


class UpdateCareTeamMemberHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        events: DomainEventPublisher,
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow = uow
        self._events = events
        self._clock = clock
        self._id_gen = id_gen

    def handle(self, cmd: UpdateCareTeamMember) -> CareTeamMemberResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: UpdateCareTeamMember) -> CareTeamMemberResult:
        member = self._uow.care_team_members.get_by_id(cmd.member_id)
        if cmd.role is not None:
            if isinstance(cmd.role, str):
                member.role = CareTeamRole(cmd.role)
            else:
                member.role = cmd.role
        if cmd.display_name is not None:
            cleaned = cmd.display_name.strip()
            if not cleaned:
                raise ValueError("Display name cannot be empty")
            member.display_name = cleaned
        if cmd.facility_id is not None:
            # Validate facility exists if provided
            self._uow.facilities.get(cmd.facility_id)
            member.facility_id = cmd.facility_id
        if cmd.active is not None:
            member.active = cmd.active

        self._uow.care_team_members.save(member)
        self._events.publish(
            CareTeamMemberUpdated(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                correlation_id=cmd.correlation_id,
                member_id=member.id,
            )
        )
        return CareTeamMemberResult(
            member_id=member.id,
            user_id=member.user_id,
            role=member.role.value,
            display_name=member.display_name,
            facility_id=member.facility_id,
            active=member.active,
        )
