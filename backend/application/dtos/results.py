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
    due_at: datetime | None = None


@dataclass(frozen=True)
class CareTaskStartedResult:
    care_task_id: UUID
    status: str


@dataclass(frozen=True)
class CareTaskReassignedResult:
    care_task_id: UUID
    assigned_to_user_id: UUID
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


@dataclass(frozen=True)
class CaregiverRelationshipRegistered:
    relationship_id: UUID
    patient_id: UUID
    status: str


@dataclass(frozen=True)
class CaregiverRelationshipVerified:
    relationship_id: UUID
    status: str
    verified_at: datetime


@dataclass(frozen=True)
class CaregiverRelationshipRevoked:
    relationship_id: UUID
    status: str


@dataclass(frozen=True)
class IdentityMappingCreated:
    mapping_id: UUID
    user_id: UUID
    patient_id: UUID
    active: bool


@dataclass(frozen=True)
class IdentityMappingDeactivated:
    mapping_id: UUID
    user_id: UUID
    active: bool


@dataclass(frozen=True)
class PatientProvisionedResult:
    patient_id: UUID
    uh_id: str
    name: str
    facility_id: UUID | None
    active: bool
    created_at: datetime


@dataclass(frozen=True)
class CareTeamMemberProvisionedResult:
    member_id: UUID
    user_id: UUID
    role: str
    display_name: str
    facility_id: UUID | None
    active: bool