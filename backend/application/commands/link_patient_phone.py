"""LinkPatientPhone command placeholder (Gate 02B).

Replaces today's binary phone-role guard with an audited, relationship-aware
phone linking use case.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from ...domain.value_objects.phone_number import PhoneNumber


@dataclass(frozen=True)
class LinkPatientPhone:
    command_id: UUID = field(default_factory=uuid4)
    patient_profile_id: UUID | None = None
    phone: PhoneNumber | None = None
    role: str = "patient"