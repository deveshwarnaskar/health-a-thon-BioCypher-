"""ConfirmGlucoseObservation use case (Gate 04).

Patient confirmation of a pending glucose observation from the WhatsApp
channel; applies the domain ``correct`` transition when a correction value is
supplied, otherwise ``confirm``. Mirrors ``ConfirmMealObservationHandler``.
"""

from ..commands import ConfirmGlucoseObservation
from ..dtos.results import ObservationConfirmedResult
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.events import GlucoseObservationConfirmed
from ._transaction import in_transaction


class ConfirmGlucoseObservationHandler:
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

    def handle(self, cmd: ConfirmGlucoseObservation) -> ObservationConfirmedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: ConfirmGlucoseObservation) -> ObservationConfirmedResult:
        observation = self._uow.glucose_observations.get(cmd.observation_id)
        if cmd.corrected_value is not None:
            observation.correct(
                by=cmd.confirmed_by,
                value=cmd.corrected_value,
                tag=cmd.corrected_tag,
                taken_at=cmd.corrected_taken_at,
            )
        else:
            observation.confirm(cmd.confirmed_by)
        self._uow.glucose_observations.save(observation)
        self._events.publish(
            GlucoseObservationConfirmed(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=observation.patient_id,
                correlation_id=cmd.correlation_id,
                observation_id=observation.id,
                source_metadata=dict(cmd.source_metadata) if cmd.source_metadata else None,
            )
        )
        return ObservationConfirmedResult(
            observation_id=observation.id,
            confirmation=observation.confirmation.value,
        )