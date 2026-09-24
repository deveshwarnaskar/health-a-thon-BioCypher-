"""AddCareTeamMember use case (Gate 10H-B).

Administrator provisioning of a care-team membership. The clinician record is
tenant-scoped by the authenticated admin's context + RLS and carries the frozen
Phase 1 role vocabulary.
"""

from ..commands import AddCareTeamMember
from ..dtos.results import CareTeamMemberProvisionedResult
from ..exceptions import DuplicateCareTeamMember
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import CareTeamMember
from ...domain.events import CareTeamMemberProvisioned
from ...domain.exceptions import EntityNotFound
from ._transaction import in_transaction


class AddCareTeamMemberHandler:
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

    def handle(self, cmd: AddCareTeamMember) -> CareTeamMemberProvisionedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: AddCareTeamMember) -> CareTeamMemberProvisionedResult:
        try:
            self._uow.care_team_members.get(cmd.user_id)
            raise DuplicateCareTeamMember(f"Care team member already exists for user {cmd.user_id}")
        except EntityNotFound:
            pass

        member = CareTeamMember(
            id=self._id_gen.new_uuid(),
            user_id=cmd.user_id,
            role=cmd.role,
            display_name=cmd.display_name,
            facility_id=cmd.facility_id,
            active=True,
        )
        self._uow.care_team_members.add(member)
        self._events.publish(
            CareTeamMemberProvisioned(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                correlation_id=cmd.correlation_id,
            )
        )
        return CareTeamMemberProvisionedResult(
            member_id=member.id,
            user_id=member.user_id,
            role=member.role.value,
            display_name=member.display_name,
            facility_id=member.facility_id,
            active=member.active,
        )