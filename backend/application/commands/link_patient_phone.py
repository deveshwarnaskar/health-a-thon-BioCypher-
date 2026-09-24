"""LinkPatientPhone command (Gate 04).

Links the patient's own phone number (patient confirmation and channel routing
use case). The value is a validated ``PhoneNumber`` value object.
"""

from dataclasses import dataclass
from uuid import UUID

from ...domain.value_objects import PhoneNumber


@dataclass(frozen=True)
class LinkPatientPhone:
    patient_id: UUID
    phone: PhoneNumber
    correlation_id: UUID | None = None