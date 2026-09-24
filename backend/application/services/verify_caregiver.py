"""VerifyCaregiverRelationship use case (Gate 08).

Advances a PENDING caregiver relationship to VERIFIED, granting proxy access
subject to the authorization policy's expiration/capability checks. Emits the
canonical ``caregiver_relationship.verified`` event.
"""

from ..commands import VerifyCaregiverRelationship
from ..dtos.results import CaregiverRelationshipVerified as CaregiverRelationshipVerifiedDTO
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.events import CaregiverRelationshipVerified as CaregiverRelationshipVerifiedEvent
from ._transaction import in_transaction


class VerifyCaregiverHandler:
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

    def handle(self, cmd: VerifyCaregiverRelationship) -> CaregiverRelationshipVerifiedDTO:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: VerifyCaregiverRelationship) -> CaregiverRelationshipVerifiedDTO:
        relationship = self._uow.caregiver_relationships.get(cmd.relationship_id)
        now = self._clock.now()
        relationship.verify(verified_at=now)
        self._uow.caregiver_relationships.save(relationship)
        self._events.publish(
            CaregiverRelationshipVerifiedEvent(
                event_id=self._id_gen.new_uuid(),
                occurred_at=now,
                patient_id=relationship.patient_id,
                correlation_id=cmd.correlation_id,
                relationship_id=relationship.id,
                caregiver_user_id=relationship.caregiver_user_id,
            )
        )
        return CaregiverRelationshipVerifiedDTO(
            relationship_id=relationship.id,
            status=relationship.status.value,
            verified_at=relationship.verified_at or now,
        )