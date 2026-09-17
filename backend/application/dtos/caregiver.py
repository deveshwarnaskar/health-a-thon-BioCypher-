"""Caregiver discovery DTOs (Gate 10E-B).

PHI-minimal, relational patient list for an EXACTLY ONE authorized caregiver
to select a patient. Carries only identifiers required to identify/select the
authorized patient plus the relationship facts. Deliberately excludes
clinician-only analytics, medication guidance, AI-review artifacts, internal
audit fields, secrets, and authentication credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Tuple
from uuid import UUID


@dataclass(frozen=True)
class CaregiverAuthorizedPatient:
    relationship_id: UUID
    patient_id: UUID
    relationship_label: str
    status: str
    capabilities: Tuple[str, ...]
    expires_at: datetime | None
    name: str


@dataclass(frozen=True)
class CaregiverPatientList:
    patient_count: int
    items: list[CaregiverAuthorizedPatient] = field(default_factory=list)