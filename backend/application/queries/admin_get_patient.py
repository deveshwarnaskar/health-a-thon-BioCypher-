"""AdminGetPatient query contract (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AdminGetPatient:
    patient_id: UUID
