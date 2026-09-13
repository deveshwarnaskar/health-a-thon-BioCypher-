"""LogMealDraft use case (Gate 04)."""

from ..commands import LogMealDraft
from ..dtos.results import MealDraftAccepted
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import MealObservation
from ...domain.events import MealObservationRecorded
from ._transaction import in_transaction


class LogMealDraftHandler:
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

    def handle(self, cmd: LogMealDraft) -> MealDraftAccepted:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: LogMealDraft) -> MealDraftAccepted:
        self._uow.patients.get(cmd.patient_id)
        observation = MealObservation(
            id=self._id_gen.new_uuid(),
            patient_id=cmd.patient_id,
            recorded_at=cmd.recorded_at,
            description=cmd.description,
            portion=cmd.portion,
            created_at=self._clock.now(),
        )
        self._uow.meal_observations.add(observation)
        self._events.publish(
            MealObservationRecorded(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=cmd.patient_id,
                correlation_id=cmd.correlation_id,
                observation_id=observation.id,
            )
        )
        return MealDraftAccepted(
            meal_observation_id=observation.id,
            patient_id=cmd.patient_id,
        )