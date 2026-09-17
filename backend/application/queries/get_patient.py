"""GetPatient query (Gate 10F-B).

Read-side input spell for one patient record. Facility is derived from the
authenticated care team membership; the handler only returns active patients
belonging to that facility.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetPatient:
    patient_id: UUID
    facility_id: UUID