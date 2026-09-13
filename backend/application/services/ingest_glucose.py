"""IngestGlucoseReading use case (Gate 04)."""

from ..commands import IngestGlucoseReading
from ..dtos.results import ObservationIngested
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import GlucoseObservation
from ...domain.events import GlucoseObservationRecorded
from ._transaction import in_transaction


class IngestGlucoseHandler:
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

    def handle(self, cmd: IngestGlucoseReading) -> ObservationIngested:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: IngestGlucoseReading) -> ObservationIngested:
        self._uow.patients.get(cmd.patient_id)
        observation = GlucoseObservation(
            id=self._id_gen.new_uuid(),
            patient_id=cmd.patient_id,
            taken_at=cmd.taken_at,
            value=cmd.value,
            tag=cmd.tag,
            created_at=self._clock.now(),
        )
        self._uow.glucose_observations.add(observation)
        self._events.publish(
            GlucoseObservationRecorded(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=cmd.patient_id,
                correlation_id=cmd.correlation_id,
                observation_id=observation.id,
            )
        )
        return ObservationIngested(
            observation_id=observation.id,
            patient_id=cmd.patient_id,
            value_mg_dl=observation.value.value_mg_dl,
            taken_at=observation.taken_at,
        )