"""RecordMedicationAdministration command (Gate 04).

Records a PATIENT medication administration/adherence event against an existing
clinician-authored MedicationPlan. This is NOT prescription and NEVER creates,
titrates, or modifies a plan — medication authority is clinician-only. The plan
must exist and be active.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...domain.value_objects import PhoneNumber


@dataclass(frozen=True)
class RecordMedicationAdministration:
    medication_plan_id: UUID
    administered_at: datetime
    recorded_by: PhoneNumber
    correlation_id: UUID | None = None