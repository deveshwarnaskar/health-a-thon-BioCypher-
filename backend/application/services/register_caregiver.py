"""RegisterCaregiverRelationship use case (Gate 08).

Creates a PENDING caregiver relationship under the active tenant. Duplicate
non-revoked relationships for the same (tenant, patient, caregiver) pair are
rejected. Emits the canonical ``caregiver_relationship.created`` event through
the transactional outbox.
"""

from ..commands import RegisterCaregiverRelationship
from ..dtos.results import CaregiverRelationshipRegistered
from ..exceptions import DuplicateCaregiverRelationship
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import CaregiverRelationship, CaregiverRelationshipStatus
from ...domain.events import CaregiverRelationshipCreated
from ._transaction import in_transaction


class RegisterCaregiverHandler:
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

    def handle(self, cmd: RegisterCaregiverRelationship) -> CaregiverRelationshipRegistered:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: RegisterCaregiverRelationship) -> CaregiverRelationshipRegistered:
        self._uow.patients.get(cmd.patient_id)

        existing = self._uow.caregiver_relationships.find_by_pair(
            cmd.caregiver_user_id, cmd.patient_id
        )
        if existing is not None and existing.status is not CaregiverRelationshipStatus.REVOKED:
            raise DuplicateCaregiverRelationship(
                "an active caregiver relationship already exists for this patient"
            )

        now = self._clock.now()
        relationship = CaregiverRelationship(
            id=self._id_gen.new_uuid(),
            patient_id=cmd.patient_id,
            caregiver_user_id=cmd.caregiver_user_id,
            relationship=cmd.relationship_label,
            status=CaregiverRelationshipStatus.PENDING,
            capabilities=frozenset(cmd.capabilities or []),
            expires_at=cmd.expires_at,
            created_at=now,
            updated_at=now,
        )
        self._uow.caregiver_relationships.add(relationship)
        self._events.publish(
            CaregiverRelationshipCreated(
                event_id=self._id_gen.new_uuid(),
                occurred_at=now,
                patient_id=cmd.patient_id,
                correlation_id=cmd.correlation_id,
                relationship_id=relationship.id,
                caregiver_user_id=cmd.caregiver_user_id,
            )
        )
        return CaregiverRelationshipRegistered(
            relationship_id=relationship.id,
            patient_id=cmd.patient_id,
            status=relationship.status.value,
        )