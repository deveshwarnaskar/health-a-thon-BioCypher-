"""CarePlan entity placeholder (Gate 02B).

Clinician-authored longitudinal plan container. Contents defined in a later gate.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CarePlan:
    id: UUID
    patient_profile_id: UUID
    authored_by_user_id: UUID
    version: int
    created_at: datetime = field(default_factory=datetime.utcnow)