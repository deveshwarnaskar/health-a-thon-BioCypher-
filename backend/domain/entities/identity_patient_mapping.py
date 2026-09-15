"""IdentityPatientMapping entity (Gate 08).

Binds a verified platform identity (the Keycloak ``sub`` acting as the
canonical ``user_id``) to exactly ONE patient within a tenant.

Management rules:

- Mappings are ADMIN-created and admin-deactivated. There is NO self-service
  endpoint that binds an identity to a patient.
- A given identity maps to at most one active patient and a given patient has
  at most one active identity mapping (enforced by partial unique database
  constraints on ``active`` rows).
- The identity link is keyed on ``user_id`` — phone-number changes NEVER
  alter an identity mapping.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class IdentityPatientMapping:
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def deactivate(self) -> None:
        self.active = False
        self.updated_at = datetime.utcnow()