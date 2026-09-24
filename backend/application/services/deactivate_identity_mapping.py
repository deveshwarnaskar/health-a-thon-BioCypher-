"""DeactivateIdentityMapping use case (Gate 08).

Administrator-managed deactivation of an identity-patient mapping. A
deactivated mapping denies patient self-access immediately.
"""

from ..commands import DeactivateIdentityMapping
from ..dtos.results import IdentityMappingDeactivated as IdentityMappingDeactivatedDTO
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.events import IdentityMappingDeactivated as IdentityMappingDeactivatedEvent
from ._transaction import in_transaction


class DeactivateIdentityMappingHandler:
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

    def handle(self, cmd: DeactivateIdentityMapping) -> IdentityMappingDeactivatedDTO:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: DeactivateIdentityMapping) -> IdentityMappingDeactivatedDTO:
        mapping = self._uow.identity_mappings.get(cmd.mapping_id)
        now = self._clock.now()
        mapping.deactivate()
        self._uow.identity_mappings.save(mapping)
        self._events.publish(
            IdentityMappingDeactivatedEvent(
                event_id=self._id_gen.new_uuid(),
                occurred_at=now,
                patient_id=mapping.patient_id,
                correlation_id=cmd.correlation_id,
                mapping_id=mapping.id,
                user_id=mapping.user_id,
            )
        )
        return IdentityMappingDeactivatedDTO(
            mapping_id=mapping.id,
            user_id=mapping.user_id,
            active=mapping.active,
        )