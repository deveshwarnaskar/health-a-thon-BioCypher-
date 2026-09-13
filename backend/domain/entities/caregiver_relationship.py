"""CaregiverRelationship entity placeholder (Gate 02B).

Patient-to-caregiver proxy authorization. Gate 01 raised whether multiple
concurrent caregivers should be supported; pending human decision.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CaregiverRelationship:
    id: UUID
    patient_profile_id: UUID
    caregiver_user_id: UUID
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)