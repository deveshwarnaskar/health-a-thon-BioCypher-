"""CreatePatient command (Gate 10H-B).

Administrator provisioning of a tenant patient record. The facility binding
comes from the authenticated admin's tenant-scoped provisioning context; the
client may only ever provide the patient identity facts, never a tenant.
"""

from dataclasses import dataclass
from uuid import UUID

from ...domain.value_objects import PhoneNumber, UHID


@dataclass(frozen=True)
class CreatePatient:
    name: str
    facility_id: UUID
    uh_id: UHID | None = None
    phone: PhoneNumber | None = None
    correlation_id: UUID | None = None