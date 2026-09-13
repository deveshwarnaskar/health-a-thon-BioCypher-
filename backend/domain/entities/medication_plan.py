"""MedicationPlan entity placeholder (Gate 02B).

Gate 01.1 correction: MedicationPlan records originate solely from licensed
clinicians; AI and patients may only record administration events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class MedicationPlan:
    id: UUID
    patient_profile_id: UUID
    prescribed_by_user_id: UUID
    created_at: datetime = field(default_factory=datetime.utcnow)