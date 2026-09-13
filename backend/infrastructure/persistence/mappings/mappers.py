"""Bidirectional mappers between pure domain entities and infrastructure models (Gate 05).

Guarantees explicit mapping boundaries:
- Domain objects remain pure stdlib dataclasses.
- Reconstructs validated domain Value Objects and enums.
- Preserves all domain fields and invariant requirements.
"""

from __future__ import annotations

from uuid import UUID

from backend.domain.entities import (
    AIReviewArtifact,
    CareTask,
    CareTeamMember,
    CareTeamRole,
    CareTaskStatus,
    GlucoseObservation,
    MealObservation,
    MedicationPlan,
    Patient,
    ReviewAuthority,
    ReviewState,
)
from backend.domain.value_objects import (
    GlucoseValue,
    KatoriVolume,
    MealPortion,
    PatientConfirmationState,
    PhoneNumber,
    ReadingTag,
    UHID,
)
from ..models import (
    AIReviewArtifactModel,
    CareTaskModel,
    CareTeamMemberModel,
    GlucoseObservationModel,
    MealObservationModel,
    MedicationPlanModel,
    PatientModel,
)


# --- Patient Mapping ---

def patient_to_domain(model: PatientModel) -> Patient:
    return Patient(
        id=model.id,
        uh_id=UHID(model.uh_id),
        name=model.name,
        phone=PhoneNumber(model.phone) if model.phone else None,
        facility_id=model.facility_id,
        active=model.active,
        created_at=model.created_at,
    )


def patient_to_model(entity: Patient, tenant_id: UUID) -> PatientModel:
    return PatientModel(
        id=entity.id,
        tenant_id=tenant_id,
        facility_id=entity.facility_id,
        uh_id=entity.uh_id.value,
        name=entity.name,
        phone=entity.phone.value if entity.phone else None,
        active=entity.active,
        created_at=entity.created_at,
    )


# --- CareTeamMember Mapping ---

def care_team_member_to_domain(model: CareTeamMemberModel) -> CareTeamMember:
    return CareTeamMember(
        id=model.id,
        user_id=model.user_id,
        role=CareTeamRole(model.role),
        display_name=model.display_name,
        facility_id=model.facility_id,
        active=model.active,
    )


def care_team_member_to_model(entity: CareTeamMember, tenant_id: UUID) -> CareTeamMemberModel:
    return CareTeamMemberModel(
        id=entity.id,
        tenant_id=tenant_id,
        user_id=entity.user_id,
        facility_id=entity.facility_id,
        role=entity.role.value,
        display_name=entity.display_name,
        active=entity.active,
    )


# --- GlucoseObservation Mapping ---

def glucose_observation_to_domain(model: GlucoseObservationModel) -> GlucoseObservation:
    return GlucoseObservation(
        id=model.id,
        patient_id=model.patient_id,
        taken_at=model.taken_at,
        value=GlucoseValue(model.value_mg_dl) if model.value_mg_dl is not None else None,
        tag=ReadingTag(model.tag) if model.tag else None,
        confirmation=PatientConfirmationState(model.confirmation),
        confirmed_by=PhoneNumber(model.confirmed_by) if model.confirmed_by else None,
        created_at=model.created_at,
    )


def glucose_observation_to_model(
    entity: GlucoseObservation, tenant_id: UUID
) -> GlucoseObservationModel:
    return GlucoseObservationModel(
        id=entity.id,
        tenant_id=tenant_id,
        patient_id=entity.patient_id,
        taken_at=entity.taken_at,
        value_mg_dl=entity.value.value_mg_dl if entity.value else None,
        tag=entity.tag.value if entity.tag else None,
        confirmation=entity.confirmation.value,
        confirmed_by=entity.confirmed_by.value if entity.confirmed_by else None,
        created_at=entity.created_at,
    )


# --- MealObservation Mapping ---

def meal_observation_to_domain(model: MealObservationModel) -> MealObservation:
    portion = None
    if model.portion_volume_ml is not None:
        portion = MealPortion(
            food_key=model.portion_food_key or "",
            katori=KatoriVolume(model.portion_volume_ml),
            quantity=model.portion_quantity if model.portion_quantity is not None else 1.0,
        )
    return MealObservation(
        id=model.id,
        patient_id=model.patient_id,
        recorded_at=model.recorded_at,
        description=model.description,
        portion=portion,
        carbs_grams=model.carbs_grams,
        glycemic_index=model.glycemic_index,
        confirmation=PatientConfirmationState(model.confirmation),
        confirmed_by=PhoneNumber(model.confirmed_by) if model.confirmed_by else None,
        created_at=model.created_at,
    )


def meal_observation_to_model(
    entity: MealObservation, tenant_id: UUID
) -> MealObservationModel:
    return MealObservationModel(
        id=entity.id,
        tenant_id=tenant_id,
        patient_id=entity.patient_id,
        recorded_at=entity.recorded_at,
        description=entity.description,
        portion_food_key=entity.portion.food_key if entity.portion else None,
        portion_volume_ml=entity.portion.katori.volume_ml if entity.portion else None,
        portion_quantity=entity.portion.quantity if entity.portion else None,
        carbs_grams=entity.carbs_grams,
        glycemic_index=entity.glycemic_index,
        confirmation=entity.confirmation.value,
        confirmed_by=entity.confirmed_by.value if entity.confirmed_by else None,
        created_at=entity.created_at,
    )


# --- MedicationPlan Mapping ---

def medication_plan_to_domain(model: MedicationPlanModel) -> MedicationPlan:
    return MedicationPlan(
        id=model.id,
        patient_id=model.patient_id,
        prescribed_by_user_id=model.prescribed_by_user_id,
        prescribed_by_role=CareTeamRole(model.prescribed_by_role),
        medication=model.medication,
        instruction=model.instruction,
        active=model.active,
        created_at=model.created_at,
    )


def medication_plan_to_model(
    entity: MedicationPlan, tenant_id: UUID
) -> MedicationPlanModel:
    return MedicationPlanModel(
        id=entity.id,
        tenant_id=tenant_id,
        patient_id=entity.patient_id,
        prescribed_by_user_id=entity.prescribed_by_user_id,
        prescribed_by_role=entity.prescribed_by_role.value,
        medication=entity.medication,
        instruction=entity.instruction,
        active=entity.active,
        created_at=entity.created_at,
    )


# --- CareTask Mapping ---

def care_task_to_domain(model: CareTaskModel) -> CareTask:
    return CareTask(
        id=model.id,
        patient_id=model.patient_id,
        assigned_to_user_id=model.assigned_to_user_id,
        description=model.description,
        status=CareTaskStatus(model.status),
        created_at=model.created_at,
        completed_at=model.completed_at,
    )


def care_task_to_model(entity: CareTask, tenant_id: UUID) -> CareTaskModel:
    return CareTaskModel(
        id=entity.id,
        tenant_id=tenant_id,
        patient_id=entity.patient_id,
        assigned_to_user_id=entity.assigned_to_user_id,
        description=entity.description,
        status=entity.status.value,
        created_at=entity.created_at,
        completed_at=entity.completed_at,
    )


# --- AIReviewArtifact Mapping ---

def ai_artifact_to_domain(model: AIReviewArtifactModel) -> AIReviewArtifact:
    return AIReviewArtifact(
        id=model.id,
        patient_id=model.patient_id,
        artifact_kind=model.artifact_kind,
        authority=ReviewAuthority(model.authority),
        state=ReviewState(model.state),
        generated_by=model.generated_by,
        summary=model.summary,
        reviewed_by_user_id=model.reviewed_by_user_id,
        created_at=model.created_at,
    )


def ai_artifact_to_model(
    entity: AIReviewArtifact, tenant_id: UUID
) -> AIReviewArtifactModel:
    return AIReviewArtifactModel(
        id=entity.id,
        tenant_id=tenant_id,
        patient_id=entity.patient_id,
        artifact_kind=entity.artifact_kind,
        authority=entity.authority.value,
        state=entity.state.value,
        generated_by=entity.generated_by,
        summary=entity.summary,
        reviewed_by_user_id=entity.reviewed_by_user_id,
        created_at=entity.created_at,
    )
