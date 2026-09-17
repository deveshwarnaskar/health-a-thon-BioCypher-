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
    CaregiverRelationship,
    CaregiverRelationshipStatus,
    Facility,
    GlucoseObservation,
    IdentityPatientMapping,
    MealObservation,
    MedicationPlan,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
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
    CaregiverRelationshipModel,
    FacilityModel,
    GlucoseObservationModel,
    IdentityPatientMappingModel,
    MealObservationModel,
    MedicationPlanModel,
    NotificationModel,
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
        due_at=model.due_at,
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
        due_at=entity.due_at,
        created_at=entity.created_at,
        completed_at=entity.completed_at,
    )


# --- AIReviewArtifact Mapping ---

def ai_artifact_to_domain(model: AIReviewArtifactModel) -> AIReviewArtifact:
    return AIReviewArtifact(
        id=model.id,
        patient_id=model.patient_id,
        tenant_id=model.tenant_id,
        artifact_kind=model.artifact_kind,
        authority=ReviewAuthority(model.authority),
        state=ReviewState(model.state),
        generated_by=model.generated_by,
        summary=model.summary,
        original_summary=model.original_summary,
        model_name=model.model_name,
        evidence_hash=model.evidence_hash,
        correlation_id=model.correlation_id,
        reviewed_by_user_id=model.reviewed_by_user_id,
        reviewed_at=model.reviewed_at,
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
        original_summary=entity.original_summary,
        model_name=entity.model_name,
        evidence_hash=entity.evidence_hash,
        correlation_id=entity.correlation_id,
        reviewed_by_user_id=entity.reviewed_by_user_id,
        reviewed_at=entity.reviewed_at,
        created_at=entity.created_at,
    )


# --- CaregiverRelationship Mapping ---

def caregiver_relationship_to_domain(model: CaregiverRelationshipModel) -> CaregiverRelationship:
    return CaregiverRelationship(
        id=model.id,
        patient_id=model.patient_id,
        caregiver_user_id=model.caregiver_user_id,
        relationship=model.relationship_label,
        status=CaregiverRelationshipStatus(model.status),
        capabilities=frozenset((model.capabilities or []) if isinstance(model.capabilities, list) else []),
        verified_at=model.verified_at,
        revoked_at=model.revoked_at,
        expires_at=model.expires_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def caregiver_relationship_to_model(
    entity: CaregiverRelationship, tenant_id: UUID
) -> CaregiverRelationshipModel:
    return CaregiverRelationshipModel(
        id=entity.id,
        tenant_id=tenant_id,
        patient_id=entity.patient_id,
        caregiver_user_id=entity.caregiver_user_id,
        relationship_label=entity.relationship,
        status=entity.status.value,
        capabilities=sorted(entity.capabilities),
        verified_at=entity.verified_at,
        revoked_at=entity.revoked_at,
        expires_at=entity.expires_at,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


# --- IdentityPatientMapping Mapping ---

def identity_patient_mapping_to_domain(model: IdentityPatientMappingModel) -> IdentityPatientMapping:
    return IdentityPatientMapping(
        id=model.id,
        user_id=model.user_id,
        patient_id=model.patient_id,
        active=model.active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def identity_patient_mapping_to_model(
    entity: IdentityPatientMapping, tenant_id: UUID
) -> IdentityPatientMappingModel:
    return IdentityPatientMappingModel(
        id=entity.id,
        tenant_id=tenant_id,
        user_id=entity.user_id,
        patient_id=entity.patient_id,
        active=entity.active,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


# --- Facility Mapping ---

def facility_to_domain(model: FacilityModel) -> Facility:
    return Facility(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        active=model.active,
        created_at=model.created_at,
    )


def facility_to_model(entity: Facility, tenant_id: UUID) -> FacilityModel:
    return FacilityModel(
        id=entity.id,
        tenant_id=tenant_id,
        name=entity.name,
        active=entity.active,
        created_at=entity.created_at,
    )


# --- Notification Mapping ---

def notification_to_domain(model: NotificationModel) -> Notification:
    return Notification(
        id=model.id,
        tenant_id=model.tenant_id,
        recipient_id=model.recipient_id,
        recipient_phone=model.recipient_phone,
        patient_id=model.patient_id,
        notification_type=NotificationType(model.notification_type),
        channel=NotificationChannel(model.channel),
        template_name=model.template_name,
        template_params=dict(model.template_params or {}),
        status=NotificationStatus(model.status),
        created_at=model.created_at,
        scheduled_at=model.scheduled_at,
        delivered_at=model.delivered_at,
        failed_at=model.failed_at,
        failure_reason=model.failure_reason,
        correlation_id=model.correlation_id,
        retry_count=model.retry_count,
    )


def notification_to_model(entity: Notification, tenant_id: UUID) -> NotificationModel:
    return NotificationModel(
        id=entity.id,
        tenant_id=tenant_id,
        recipient_id=entity.recipient_id,
        recipient_phone=entity.recipient_phone,
        patient_id=entity.patient_id,
        notification_type=entity.notification_type.value if hasattr(entity.notification_type, "value") else str(entity.notification_type),
        channel=entity.channel.value if hasattr(entity.channel, "value") else str(entity.channel),
        template_name=entity.template_name,
        template_params=dict(entity.template_params or {}),
        status=entity.status.value if hasattr(entity.status, "value") else str(entity.status),
        created_at=entity.created_at,
        scheduled_at=entity.scheduled_at,
        delivered_at=entity.delivered_at,
        failed_at=entity.failed_at,
        failure_reason=entity.failure_reason,
        correlation_id=entity.correlation_id,
        retry_count=entity.retry_count,
    )

