"""Clinician read-contract DTOs (Gate 10F-B).

CLINICIAN-ONLY read result types for the Doctor/P.L.A.T.E. mobile slice:

- AI review artifact queue and detail (clinician review evidence only)
- medication plan list and detail (clinician-authored plans)
- patient cohort list and detail

These DTOs surface ONLY through authorized clinician workflows. Patient-facing
interfaces must never receive these types, and proxy roles (patient/caregiver)
are denied at the HTTP authorization boundary before any handler runs. Medical
instructions (``instruction``) contained in medication plans are
clinician-authored and remain within clinician-scoped reads only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AIReviewArtifactRecord:
    artifact_id: UUID
    patient_id: UUID
    artifact_kind: str
    state: str
    summary: str
    created_at: datetime


@dataclass(frozen=True)
class AIReviewArtifactList:
    artifact_count: int
    items: list[AIReviewArtifactRecord] = field(default_factory=list)


@dataclass(frozen=True)
class MedicationPlanRecord:
    medication_plan_id: UUID
    patient_id: UUID
    medication: str
    instruction: str
    active: bool
    prescribed_by_role: str
    created_at: datetime


@dataclass(frozen=True)
class MedicationPlanList:
    plan_count: int
    items: list[MedicationPlanRecord] = field(default_factory=list)


@dataclass(frozen=True)
class PatientRecord:
    patient_id: UUID
    uh_id: str
    name: str
    facility_id: UUID | None
    active: bool
    created_at: datetime


@dataclass(frozen=True)
class PatientList:
    patient_count: int
    items: list[PatientRecord] = field(default_factory=list)