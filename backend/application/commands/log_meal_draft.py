"""LogMealDraft command (Gate 04).

A meal submitted by the patient/caregiver that has NOT yet been confirmed.
Confirmation is a separate use case.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...domain.value_objects import MealPortion


@dataclass(frozen=True)
class LogMealDraft:
    patient_id: UUID
    description: str
    recorded_at: datetime
    portion: MealPortion | None = None
    correlation_id: UUID | None = None