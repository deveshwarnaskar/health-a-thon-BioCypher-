"""ConfirmMealObservation command (Gate 04).

Patient confirmation of an extracted/drafted meal observation. Optional
correction applies the domain ``correct`` transition when the patient edits
description/portion; otherwise the observation is simply confirmed.
"""

from dataclasses import dataclass
from uuid import UUID

from ...domain.value_objects import MealPortion, PhoneNumber


@dataclass(frozen=True)
class ConfirmMealObservation:
    meal_observation_id: UUID
    confirmed_by: PhoneNumber
    corrected_description: str | None = None
    corrected_portion: MealPortion | None = None
    correlation_id: UUID | None = None