"""GetClinicalObservationFeed query (Gate 04).

Clinician-only timeline (P.L.A.T.E. clinical work is Phase 2). Returns
CLINICAL records including clinician-only analytical fields (carbohydrate grams,
glycemic index). Intentionally a separate DTO from the patient-facing feed so
the two information boundaries never collapse.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class GetClinicalObservationFeed:
    patient_id: UUID
    clinician_user_id: UUID
    limit: int = 50
    query_id: UUID = field(default_factory=uuid4)