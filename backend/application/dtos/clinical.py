"""Clinician-only DTOs (Gate 04).

Intentionally SEPARATE from patient-facing DTOs. These records expose
clinician-only analytical fields and may ONLY surface through authorized
clinician workflows (P.L.A.T.E. clinical web is Phase 2). Patient-facing
interfaces must never receive this type.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ClinicalMealRecord:
    observation_id: UUID
    description: str
    portion_label: str | None
    quantity: float | None
    carbs_grams: float | None
    glycemic_index: str | None
    recorded_at: datetime
    confirmation: str


@dataclass(frozen=True)
class ClinicalGlucoseRecord:
    observation_id: UUID
    value_mg_dl: int | None
    tag: str | None
    taken_at: datetime
    confirmation: str


@dataclass(frozen=True)
class ClinicalObservationFeed:
    patient_id: object
    items: list[object] = field(default_factory=list)