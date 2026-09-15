"""CreateIdentityMapping command (Gate 08).

Administrator-managed binding of a verified platform identity (user_id) to a
tenant patient. There is NO self-service equivalent.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateIdentityMapping:
    user_id: UUID
    patient_id: UUID
    correlation_id: UUID | None = None