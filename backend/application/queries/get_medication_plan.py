"""GetMedicationPlan query (Gate 10F-B).

Read-side input spell for one clinician-authored medication plan. Facility is
derived from the authenticated care team membership; the handler only returns
plans whose patient belongs to that facility and is active.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetMedicationPlan:
    plan_id: UUID
    facility_id: UUID