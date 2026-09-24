"""DeactivateCareTeamMember use case (Gate 10K-B)."""

from backend.application.commands.deactivate_care_team_member import DeactivateCareTeamMember
from backend.application.dtos.admin import CareTeamMemberResult
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services._transaction import in_transaction
from backend.domain.events.admin import CareTeamMemberDeactivated


class DeactivateCareTeamMemberHandler:
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

    def handle(self, cmd: DeactivateCareTeamMember) -> CareTeamMemberResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: DeactivateCareTeamMember) -> CareTeamMemberResult:
        member = self._uow.care_team_members.get_by_id(cmd.member_id)
        member.deactivate()
        self._uow.care_team_members.save(member)
        self._events.publish(
            CareTeamMemberDeactivated(
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
