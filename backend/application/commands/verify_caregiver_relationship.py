"""VerifyCaregiverRelationship command (Gate 08).

Advances a PENDING caregiver relationship to VERIFIED. Only a clinician
authorized for the patient may issue this command (enforced at the HTTP
boundary by the authorization policy).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VerifyCaregiverRelationship:
    relationship_id: UUID
    correlation_id: UUID | None = None