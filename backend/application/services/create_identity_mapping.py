"""CreateIdentityMapping use case (Gate 08).

Administrator-managed binding of a verified platform identity to a tenant
patient. Active mappings are 1:1 in both directions (one mapping per user,
one per patient). Duplicate active bindings are rejected.
"""

from ..commands import CreateIdentityMapping
from ..dtos.results import IdentityMappingCreated as IdentityMappingCreatedDTO
from ..exceptions import DuplicateIdentityMapping
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import IdentityPatientMapping
from ...domain.events import IdentityMappingCreated as IdentityMappingCreatedEvent
from ._transaction import in_transaction


class CreateIdentityMappingHandler:
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

    def handle(self, cmd: CreateIdentityMapping) -> IdentityMappingCreatedDTO:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: CreateIdentityMapping) -> IdentityMappingCreatedDTO:
        self._uow.patients.get(cmd.patient_id)

        by_user = self._uow.identity_mappings.get_by_user_id(cmd.user_id)
        if by_user is not None and by_user.active:
            raise DuplicateIdentityMapping("this user already has an active identity mapping")

        by_patient = self._uow.identity_mappings.get_by_patient_id(cmd.patient_id)
        if by_patient is not None and by_patient.active:
            raise DuplicateIdentityMapping("this patient already has an active identity mapping")

        now = self._clock.now()
        mapping = IdentityPatientMapping(
            id=self._id_gen.new_uuid(),
            user_id=cmd.user_id,
            patient_id=cmd.patient_id,
            active=True,
            created_at=now,
            updated_at=now,
        )
        self._uow.identity_mappings.add(mapping)
        self._events.publish(
            IdentityMappingCreatedEvent(
                event_id=self._id_gen.new_uuid(),
                occurred_at=now,
                patient_id=cmd.patient_id,
                correlation_id=cmd.correlation_id,
                mapping_id=mapping.id,
                user_id=cmd.user_id,
            )
        )
        return IdentityMappingCreatedDTO(
            mapping_id=mapping.id,
            user_id=cmd.user_id,
            patient_id=cmd.patient_id,
            active=mapping.active,
        )