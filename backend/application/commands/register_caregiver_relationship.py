"""RegisterCaregiverRelationship command (Gate 08).

Creates a PENDING caregiver relationship for a patient. Verification is a
separate, clinician-mediated step. Command input spells are frozen dataclasses.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RegisterCaregiverRelationship:
    patient_id: UUID
    caregiver_user_id: UUID
    relationship_label: str
    capabilities: frozenset[str] = frozenset()
    expires_at: datetime | None = None
    correlation_id: UUID | None = None