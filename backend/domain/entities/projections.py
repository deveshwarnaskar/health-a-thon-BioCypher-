"""Patient-facing projections (Gate 03).

CLINICAL INFORMATION ASYMMETRY — CRITICAL INVARIANT.

Patient-facing projections are the ONLY shapes allowed to reach patients. They
must never expose clinician-only analytical fields such as carbohydrate grams,
glycemic index, or macronutrient analysis. The invariant is enforced by the
projection shape itself (the fields simply do not exist), not by hiding fields
in the frontend.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PatientFacingMealObservation:
    description: str
    portion_label: str | None
    quantity: float | None
    recorded_at: datetime
    confirmed: bool


@dataclass(frozen=True)
class PatientFacingGlucoseObservation:
    value_mg_dl: int | None
    tag: str | None
    taken_at: datetime
    confirmed: bool