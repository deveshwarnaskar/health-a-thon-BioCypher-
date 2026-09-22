"""ConfirmMealObservation use case (Gate 04).

Patient confirmation of a pending meal observation; applies the domain
``correct`` transition when a correction is supplied, otherwise ``confirm``.
"""

from ..commands import ConfirmMealObservation
from ..dtos.results import MealObservationConfirmedResult
from ..ports.events import DomainEventPublisher
from ..ports.clock import Clock
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.events import MealObservationConfirmed
from ...domain.exceptions import DomainError
from ...domain.services.carbohydrate_calculator import CarbohydrateCalculator
from ._transaction import in_transaction


class ConfirmMealObservationHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        events: DomainEventPublisher,
        clock: Clock,
        id_gen: IdGenerator,
        calculator: CarbohydrateCalculator | None = None,
    ) -> None:
        self._uow = uow
        self._events = events
        self._clock = clock
        self._id_gen = id_gen
        self._calculator = calculator or CarbohydrateCalculator()

    def handle(self, cmd: ConfirmMealObservation) -> MealObservationConfirmedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: ConfirmMealObservation) -> MealObservationConfirmedResult:
        observation = self._uow.meal_observations.get(cmd.meal_observation_id)
        if cmd.corrected_description is not None or cmd.corrected_portion is not None:
            description = cmd.corrected_description or observation.description
            portion = cmd.corrected_portion or observation.portion
            observation.correct(description, portion)
        else:
            observation.confirm(cmd.confirmed_by)
        if observation.portion is not None:
            try:
                calc = self._calculator.calculate_for_portion(observation.portion)
                observation.carbs_grams = calc.carbs_grams
                observation.glycemic_index = calc.glycemic_index
            except DomainError:
                from ...infrastructure.parsing.nutrition_taxonomy import (
                    classify_text,
                    estimate_nutrition,
                )
                items = classify_text(observation.description)
                if items:
                    portion_letter = "m"
                    if observation.portion.katori.volume_ml == 150:
                        portion_letter = "s"
                    elif observation.portion.katori.volume_ml == 350:
                        portion_letter = "l"
                    nutrition = estimate_nutrition(items, portion_letter)
                    observation.carbs_grams = nutrition.carbs_grams
                    observation.glycemic_index = nutrition.gi_category
        self._uow.meal_observations.save(observation)
        self._events.publish(
            MealObservationConfirmed(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=observation.patient_id,
                correlation_id=cmd.correlation_id,
                observation_id=observation.id,
                source_metadata=dict(cmd.source_metadata) if cmd.source_metadata else None,
            )
        )
        return MealObservationConfirmedResult(
            meal_observation_id=observation.id,
            confirmation=observation.confirmation.value,
        )