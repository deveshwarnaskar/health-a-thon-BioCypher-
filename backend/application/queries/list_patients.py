"""ListPatients query (Gate 10F-B).

Read-side input spell for the clinician patient cohort. Facility is derived
from the authenticated care team membership by the route — never from a
client-supplied value.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListPatients:
    facility_id: UUID
    limit: int = 50