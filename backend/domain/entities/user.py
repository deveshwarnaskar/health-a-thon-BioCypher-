"""User entity placeholder (Gate 02B).

Role references the RBAC model agreed in Gate 01 (Patient, Caregiver, Doctor,
Nurse, Care Coordinator, Dietitian/Diabetes Educator, Field Health Worker).
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class User:
    id: UUID
    external_identity_sub: str
    display_name: str
    role: str
    created_at: datetime = field(default_factory=datetime.utcnow)