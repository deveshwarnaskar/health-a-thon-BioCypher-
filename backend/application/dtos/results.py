"""Command result DTOs (Gate 04).

Small frozen view models returned by application use cases. They describe the
result of orchestration, not the entire domain aggregate.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ObservationIngested:
    observation_id: UUID
    patient_id: UUID
    value_mg_dl: int
    taken_at: datetime


@dataclass(frozen=True)
class PhoneLinked:
    patient_id: UUID
    phone_masked: str


@dataclass(frozen=True)
class MealDraftAccepted:
    meal_observation_id: UUID
    patient_id: UUID


@dataclass(frozen=True)
class MealObservationConfirmedResult:
    meal_observation_id: UUID
    confirmation: str


@dataclass(frozen=True)
class AdministrationRecorded:
    medication_plan_id: UUID
    patient_id: UUID
    administered_at: datetime


@dataclass(frozen=True)
class CareTaskCreatedResult:
    care_task_id: UUID
    patient_id: UUID
    status: str


@dataclass(frozen=True)
class CareTaskCompletedResult:
    care_task_id: UUID
    status: str
    completed_at: datetime


@dataclass(frozen=True)
class MedicationPlanCreated:
    medication_plan_id: UUID
    patient_id: UUID


@dataclass(frozen=True)
class AIArtifactGeneratedResult:
    artifact_id: UUID
    patient_id: UUID
    state: str
    summary: str


@dataclass(frozen=True)
class AIArtifactReviewedResult:
    artifact_id: UUID
    state: str
    reviewed_by_user_id: UUID