"""CaregiverRelationship entity (Gate 03).

Patient-to-caregiver proxy authorization with an explicit relationship label
and a revoke-only lifecycle (a revoked relationship cannot be re-revoked).
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from ..exceptions import InvalidRelationship


@dataclass
class CaregiverRelationship:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    caregiver_user_id: UUID = field(default_factory=uuid4)
    relationship: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not isinstance(self.relationship, str) or not self.relationship.strip():
            raise InvalidRelationship("caregiver relationship label is required")

    def revoke(self) -> None:
        if not self.active:
            raise InvalidRelationship("caregiver relationship is already revoked")
        self.active = False