"""LogMealDraft command (Gate 04).

A meal submitted by the patient/caregiver that has NOT yet been confirmed.
Confirmation is a separate use case.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from ...domain.value_objects import MealPortion


@dataclass(frozen=True)
class LogMealDraft:
    patient_id: UUID
    description: str
    recorded_at: datetime
    portion: MealPortion | None = None
    correlation_id: UUID | None = None
    # Nutrition pre-computed by the Hinglish parser (doctor-only)
    carbs_grams: float | None = None
    gi_category: str | None = None
    # Parsed food items for reply composition (not persisted directly)
    classified_items: tuple[Any, ...] = field(default_factory=tuple)
    # Ambiguity flags — handler sends clarification instead of meal proposal
    is_ambiguous: bool = False
    ambiguous_candidates: tuple[float, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Freeze mutable defaults to tuples (dataclass frozen=True requires hashable)
        object.__setattr__(self, "classified_items", tuple(self.classified_items))
        object.__setattr__(self, "ambiguous_candidates", tuple(self.ambiguous_candidates))
