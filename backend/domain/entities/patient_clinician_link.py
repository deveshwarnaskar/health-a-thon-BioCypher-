"""PatientClinicianLink entity (patient-doctor QR connect, Gate 13).

A durable, bidirectional patient↔clinician connection established by a
patient scanning a clinician's account QR code. The link:

- binds one patient to one clinician user within the tenant,
- snapshots the clinician's facility (the patient is enrolled there so the
  clinician's facility-scoped reads/monitoring can resolve the patient),
- snapshots the clinician's display name for patient-facing "My Care Team".

``active`` is a persistent lifecycle flag; a deactivated link stops being
listed for the patient. There is no separate consent step — scanning IS the
consent (the patient initiates it).
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class PatientClinicianLink:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    clinician_user_id: UUID = field(default_factory=uuid4)
    facility_id: UUID | None = None
    clinician_name: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def activate(self) -> None:
        self.active = True
        self.updated_at = datetime.utcnow()

    def deactivate(self) -> None:
        self.active = False
        self.updated_at = datetime.utcnow()