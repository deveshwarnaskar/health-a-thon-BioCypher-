"""GetPatientObservationFeed query (Gate 04).

Patient-facing timeline. Returns ONLY patient-facing projections (plain meal
facts and glucose values) — never carbohydrate grams, glycemic index, or any
clinician-only synthesis.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetPatientObservationFeed:
    patient_id: UUID
    limit: int = 50