"""ListMedicationPlans query (Gate 10F-B).

Read-side input spell for the clinician medication-plan list. Facility is
derived from the authenticated care team membership by the route — never from
a client-supplied value.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListMedicationPlans:
    facility_id: UUID
    limit: int = 50