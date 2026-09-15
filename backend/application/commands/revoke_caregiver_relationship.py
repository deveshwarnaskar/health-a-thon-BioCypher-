"""RevokeCaregiverRelationship command (Gate 08).

Immediately revokes a caregiver relationship, removing proxy access regardless
of verification state.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RevokeCaregiverRelationship:
    relationship_id: UUID
    correlation_id: UUID | None = None