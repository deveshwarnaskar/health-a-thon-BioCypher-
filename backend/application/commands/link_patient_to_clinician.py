"""LinkPatientToClinician command (Gate 13).

Patients initiate a bidirectional connection to a clinician by scanning the
clinician's account QR code. Command input spells are frozen dataclasses.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class LinkPatientToClinician:
    patient_id: UUID
    clinician_user_id: UUID
    correlation_id: UUID | None = None