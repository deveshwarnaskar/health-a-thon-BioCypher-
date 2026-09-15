"""RevokeCaregiverRelationship use case (Gate 08).

Immediately revokes a caregiver relationship regardless of pending/verified
state. Revocation is final and cannot be re-revoked. Emits the canonical
``caregiver_relationship.revoked`` event.
"""

from ..commands import RevokeCaregiverRelationship
from ..dtos.results import CaregiverRelationshipRevoked as CaregiverRelationshipRevokedDTO
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.events import CaregiverRelationshipRevoked as CaregiverRelationshipRevokedEvent
from ._transaction import in_transaction


class RevokeCaregiverHandler:
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

    def handle(self, cmd: RevokeCaregiverRelationship) -> CaregiverRelationshipRevokedDTO:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: RevokeCaregiverRelationship) -> CaregiverRelationshipRevokedDTO:
        relationship = self._uow.caregiver_relationships.get(cmd.relationship_id)
        now = self._clock.now()
        relationship.revoke()
        self._uow.caregiver_relationships.save(relationship)
        self._events.publish(
            CaregiverRelationshipRevokedEvent(
                event_id=self._id_gen.new_uuid(),
                occurred_at=now,
                patient_id=relationship.patient_id,
                correlation_id=cmd.correlation_id,
                relationship_id=relationship.id,
                caregiver_user_id=relationship.caregiver_user_id,
            )
        )
        return CaregiverRelationshipRevokedDTO(
            relationship_id=relationship.id,
            status=relationship.status.value,
        )