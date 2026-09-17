"""CreateFacility use case (Gate 10K-B)."""

from backend.application.commands.create_facility import CreateFacility
from backend.application.dtos.admin import FacilityResult
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services._transaction import in_transaction
from backend.domain.entities.facility import Facility
from backend.domain.events.admin import FacilityCreated


class CreateFacilityHandler:
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

    def handle(self, cmd: CreateFacility) -> FacilityResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: CreateFacility) -> FacilityResult:
        facility = Facility(
            id=self._id_gen.new_uuid(),
            tenant_id=getattr(self._uow, "tenant_id", self._id_gen.new_uuid()),
            name=cmd.name.strip(),
            active=True,
            created_at=self._clock.now(),
        )
        self._uow.facilities.add(facility)
        self._events.publish(
            FacilityCreated(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                correlation_id=cmd.correlation_id,
                facility_id=facility.id,
            )
        )
        return FacilityResult(
            facility_id=facility.id,
            tenant_id=facility.tenant_id,
            name=facility.name,
            active=facility.active,
            created_at=facility.created_at,
        )
