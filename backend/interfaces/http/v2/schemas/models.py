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


# ─── Error ──────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    error: dict