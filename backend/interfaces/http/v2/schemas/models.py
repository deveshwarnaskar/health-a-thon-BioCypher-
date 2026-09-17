"""HTTP request/response schemas (Gate 07).

Pydantic v2 models for the API boundary. These are SEPARATE from:
- domain entities
- ORM models
- persistence models

Patient-facing schemas MUST NOT contain:
- carbohydrate grams
- glycemic index
- clinical nutrition analytics

Clinician-facing schemas may contain the analytics allowed by existing contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


_STRICT = ConfigDict(extra="forbid")


# ─── Auth ────────────────────────────────────────────────────────────────────


class AuthVerifyResponse(BaseModel):
    model_config = _STRICT
    actor_id: str
    tenant_id: str
    roles: list[str]
    facility_id: str | None = None


# ─── Glucose Observation (Patient-Facing) ───────────────────────────────────


class PatientGlucoseObservationResponse(BaseModel):
    kind: Literal["glucose"] = "glucose"
    value_mg_dl: int | None = None
    tag: str | None = None
    taken_at: datetime
    confirmed: bool


# ─── Meal Observation (Patient-Facing) ──────────────────────────────────────


class PatientMealObservationResponse(BaseModel):
    kind: Literal["meal"] = "meal"
    description: str
    portion_label: str | None = None
    quantity: float | None = None
    recorded_at: datetime
    confirmed: bool


# Patient-facing response MUST NOT contain carbs_grams, glycemic_index


class PatientObservationFeedResponse(BaseModel):
    patient_id: str
    items: list[PatientGlucoseObservationResponse | PatientMealObservationResponse]


# ─── Glucose Observation (Clinician-Facing) ─────────────────────────────────


class ClinicalGlucoseObservationResponse(BaseModel):
    kind: Literal["glucose"] = "glucose"
    observation_id: str
    value_mg_dl: int | None = None
    tag: str | None = None
    taken_at: datetime
    confirmation: str


# ─── Meal Observation (Clinician-Facing) ────────────────────────────────────


class ClinicalMealObservationResponse(BaseModel):
    kind: Literal["meal"] = "meal"
    observation_id: str
    description: str
    portion_label: str | None = None
    quantity: float | None = None
    carbs_grams: float | None = None
    glycemic_index: str | None = None
    recorded_at: datetime
    confirmation: str


class ClinicalObservationFeedResponse(BaseModel):
    patient_id: str
    items: list[ClinicalGlucoseObservationResponse | ClinicalMealObservationResponse]


# ─── Glucose Ingestion ──────────────────────────────────────────────────────


class IngestGlucoseRequest(BaseModel):
    model_config = _STRICT
    patient_id: UUID
    value_mg_dl: int = Field(ge=20, le=600)
    tag: str | None = None
    taken_at: datetime | None = None


class IngestGlucoseResponse(BaseModel):
    observation_id: str
    patient_id: str
    value_mg_dl: int
    taken_at: datetime


# ─── Medication Plan ────────────────────────────────────────────────────────


class MedicationPlanResponse(BaseModel):
    medication_plan_id: str
    patient_id: str
    medication: str
    instruction: str
    active: bool
    prescribed_by_role: str
    created_at: datetime


class CreateMedicationPlanRequest(BaseModel):
    model_config = _STRICT
    patient_id: UUID
    medication: str = Field(min_length=1)
    instruction: str = ""


class CreateMedicationPlanResponse(BaseModel):
    medication_plan_id: str
    patient_id: str


# ─── AI Artifact ────────────────────────────────────────────────────────────


class AIArtifactResponse(BaseModel):
    artifact_id: str
    patient_id: str
    artifact_kind: str
    state: str
    summary: str
    created_at: datetime


class GenerateAIArtifactRequest(BaseModel):
    model_config = _STRICT
    patient_id: UUID
    context: str = ""


class GenerateAIArtifactResponse(BaseModel):
    artifact_id: str
    patient_id: str
    state: str
    summary: str


class ReviewAIArtifactRequest(BaseModel):
    model_config = _STRICT
    decision: Literal["approve", "edit", "reject"]
    edited_summary: str | None = None


class ReviewAIArtifactResponse(BaseModel):
    artifact_id: str
    state: str
    reviewed_by_user_id: str


# ─── WhatsApp Webhook ───────────────────────────────────────────────────────


class WhatsAppVerifyResponse(BaseModel):
    challenge: str


class WhatsAppInboundResponse(BaseModel):
    status: str = "received"
    message: str = "Webhook event accepted for processing"


# ─── Caregiver Relationship (Gate 08) ────────────────────────────────────────


class CaregiverRelationshipResponse(BaseModel):
    model_config = _STRICT
    relationship_id: str
    patient_id: str
    caregiver_user_id: str
    relationship_label: str
    status: Literal["pending", "verified", "revoked", "expired"]
    capabilities: list[str]
    verified_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class CaregiverRelationshipListResponse(BaseModel):
    model_config = _STRICT
    patient_id: str
    items: list[CaregiverRelationshipResponse]


class RegisterCaregiverRequest(BaseModel):
    model_config = _STRICT
    caregiver_user_id: UUID
    relationship_label: str = Field(min_length=1)
    capabilities: list[str] = []
    expires_at: datetime | None = None


# ─── Caregiver Patient Discovery (Gate 10E-B) ───────────────────────────────


class CaregiverPatientListItemResponse(BaseModel):
    """One authorized patient the caregiver may select.

    Patient-selection/relationship facts ONLY: no carbohydrate analytics,
    glucose summaries, risk scores, treatment guidance, medication dosage
    instructions, AI-review artifacts, internal audit fields, or credentials.
    """

    model_config = _STRICT
    relationship_id: str
    patient_id: str
    relationship_label: str
    status: Literal["verified"]
    capabilities: list[str]
    expires_at: datetime | None = None
    name: str


class CaregiverPatientListResponse(BaseModel):
    model_config = _STRICT
    patient_count: int
    items: list[CaregiverPatientListItemResponse]


# ─── Clinician Read Contracts (Gate 10F-B) ───────────────────────────────────


class AIArtifactListResponse(BaseModel):
    """Clinician pending-review queue (Gate 10F-B).

    List of AI review artifacts requiring human clinical review. Only
    authorization-boundary + review-facts are exposed: no credentials, internal
    audit fields, or generation internals.
    """

    model_config = _STRICT
    artifact_count: int
    items: list[AIArtifactResponse]


class MedicationPlanListResponse(BaseModel):
    """Clinician medication-plan list (Gate 10F-B).

    Clinician-authored medication plans. Medical instructions are exposed ONLY
    through authenticated clinician reads — patient-facing and caregiver-facing
    schemas must never receive this type.
    """

    model_config = _STRICT
    plan_count: int
    items: list[MedicationPlanResponse]


class PatientSummaryResponse(BaseModel):
    """One patient record for a facility-scoped clinician read (Gate 10F-B).

    Identity/lifecycle facts only: no observations, no clinical analytics,
    no medication guidance, no AI-review artifacts, no audit or internal
    fields. Deliberately excludes phone (PHI-light) so a cohort read exposes
    the minimum surface required for patient selection.
    """

    model_config = _STRICT
    patient_id: str
    uh_id: str
    name: str
    facility_id: str | None = None
    active: bool
    created_at: datetime


class PatientListResponse(BaseModel):
    """Facility-scoped clinician patient cohort (Gate 10F-B)."""

    model_config = _STRICT
    patient_count: int
    items: list[PatientSummaryResponse]


# ─── Identity Patient Mapping (Gate 08) ─────────────────────────────────────


class CreateIdentityMappingRequest(BaseModel):
    model_config = _STRICT
    user_id: UUID
    patient_id: UUID


class IdentityMappingResponse(BaseModel):
    model_config = _STRICT
    mapping_id: str
    user_id: str
    patient_id: str
    active: bool
    created_at: datetime


# ─── Meal Documentation (Gate 10H-B) ─────────────────────────────────────────


class MealPortionRequest(BaseModel):
    """Canonical Aahaar volumetric portion vocabulary (Gate 10H-B).

    Patient-facing: description/portion ONLY. NEVER carries carbohydrate grams
    or glycemic index — that analytic interpretation remains clinician-scoped.
    """

    model_config = _STRICT
    food_key: str = Field(min_length=1)
    katori_volume_ml: Literal[150, 220, 350]
    quantity: float = Field(default=1.0, ge=0.1, le=100)


class LogMealRequest(BaseModel):
    model_config = _STRICT
    patient_id: UUID
    description: str = Field(min_length=1)
    portion: MealPortionRequest | None = None
    recorded_at: datetime | None = None


class LogMealResponse(BaseModel):
    model_config = _STRICT
    meal_observation_id: str
    patient_id: str
    portion_label: str | None = None
    quantity: float | None = None


class ConfirmMealRequest(BaseModel):
    model_config = _STRICT
    corrected_description: str | None = None
    corrected_portion: MealPortionRequest | None = None


class ConfirmMealResponse(BaseModel):
    model_config = _STRICT
    meal_observation_id: str
    patient_id: str
    confirmation: str


# ─── Medication Administration (Gate 10H-B) ─────────────────────────────────


class RecordMedicationAdministrationRequest(BaseModel):
    model_config = _STRICT
    medication_plan_id: UUID
    administered_at: datetime | None = None


class RecordMedicationAdministrationResponse(BaseModel):
    model_config = _STRICT
    medication_plan_id: str
    patient_id: str
    administered_at: datetime


# ─── Care Tasks (Gate 10H-B) ────────────────────────────────────────────────


class CareTaskResponse(BaseModel):
    model_config = _STRICT
    care_task_id: str
    patient_id: str
    assigned_to_user_id: str
    description: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None


class CareTaskListResponse(BaseModel):
    model_config = _STRICT
    patient_id: str
    task_count: int
    items: list[CareTaskResponse]


class CreateCareTaskRequest(BaseModel):
    model_config = _STRICT
    patient_id: UUID
    assigned_to_user_id: UUID
    description: str = Field(min_length=1)


class CompleteCareTaskResponse(BaseModel):
    model_config = _STRICT
    care_task_id: str
    status: str
    completed_at: datetime


# ─── Administrative Provisioning (Gate 10H-B) ──────────────────────────────


class ProvisionPatientRequest(BaseModel):
    """Administrator provisioning of a tenant patient record.

    ``facility_id`` is accepted as a well-formed UUID. The authoritative
    tenant remains the JWT claim — never a client field. The platform has no
    facility repository port, so facility existence is NOT verified here
    (fail-closed posture documented; unknown facilities yield an unscoped
    patient that no clinician can reach).
    """

    model_config = _STRICT
    name: str = Field(min_length=1)
    uh_id: str | None = Field(default=None, max_length=64)
    facility_id: UUID
    phone: str | None = None


class ProvisionPatientResponse(BaseModel):
    model_config = _STRICT
    patient_id: str
    uh_id: str
    name: str
    facility_id: str | None = None
    active: bool
    created_at: datetime


class ProvisionCareTeamMemberRequest(BaseModel):
    model_config = _STRICT
    user_id: UUID
    role: Literal[
        "doctor",
        "nurse",
        "care_coordinator",
        "dietitian",
        "field_health_worker",
    ]
    display_name: str = Field(min_length=1)
    facility_id: UUID


class CareTeamMemberResponse(BaseModel):
    model_config = _STRICT
    member_id: str
    user_id: str
    role: str
    display_name: str
    facility_id: str | None = None
    active: bool


# ─── Error ──────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    error: dict