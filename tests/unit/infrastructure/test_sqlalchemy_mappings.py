"""Tests for SQLAlchemy mapping boundaries and round-trip conversion (Gate 05).

Verifies:
1. Domain entity -> Model -> Domain entity preserves all invariants and fields.
2. Value Objects (UHID, PhoneNumber, GlucoseValue, ReadingTag, MealPortion, KatoriVolume)
   are correctly converted and reconstructed.
3. Clinician authority and clinical asymmetry fields are preserved.
4. Domain entities never inherit from SQLAlchemy Base.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

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
from backend.infrastructure.persistence.mappings import (
    ai_artifact_to_domain,
    ai_artifact_to_model,
    care_task_to_domain,
    care_task_to_model,
    care_team_member_to_domain,
    care_team_member_to_model,
    glucose_observation_to_domain,
    glucose_observation_to_model,
    meal_observation_to_domain,
    meal_observation_to_model,
    medication_plan_to_domain,
    medication_plan_to_model,
    patient_to_domain,
    patient_to_model,
)
from backend.infrastructure.persistence.models.base import Base


def test_domain_entities_do_not_inherit_from_sqlalchemy_base():
    for cls in [
        Patient,
        CareTeamMember,
        GlucoseObservation,
        MealObservation,
        MedicationPlan,
        CareTask,
        AIReviewArtifact,
    ]:
        assert not issubclass(cls, Base), f"{cls.__name__} must remain pure stdlib dataclass"


def test_patient_mapping_roundtrip():
    tenant_id = uuid4()
    patient = Patient(
        id=uuid4(),
        uh_id=UHID("UHID-12345"),
        name="Sunita Sharma",
        phone=PhoneNumber("+919876543210"),
        facility_id=uuid4(),
        active=True,
        created_at=datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
    )

    model = patient_to_model(patient, tenant_id)
    assert model.id == patient.id
    assert model.tenant_id == tenant_id
    assert model.uh_id == "UHID-12345"
    assert model.phone == "+919876543210"

    restored = patient_to_domain(model)
    assert restored.id == patient.id
    assert restored.uh_id.value == "UHID-12345"
    assert restored.name == "Sunita Sharma"
    assert restored.phone is not None
    assert restored.phone.value == "+919876543210"
    assert restored.facility_id == patient.facility_id
    assert restored.active is True
    assert restored.created_at == patient.created_at


def test_care_team_member_mapping_roundtrip():
    tenant_id = uuid4()
    member = CareTeamMember(
        id=uuid4(),
        user_id=uuid4(),
        role=CareTeamRole.DOCTOR,
        display_name="Dr. Mehta",
        facility_id=uuid4(),
        active=True,
    )

    model = care_team_member_to_model(member, tenant_id)
    assert model.tenant_id == tenant_id
    assert model.role == "doctor"

    restored = care_team_member_to_domain(model)
    assert restored.id == member.id
    assert restored.user_id == member.user_id
    assert restored.role == CareTeamRole.DOCTOR
    assert restored.display_name == "Dr. Mehta"
    assert restored.facility_id == member.facility_id
    assert restored.active is True


def test_glucose_observation_mapping_roundtrip():
    tenant_id = uuid4()
    obs = GlucoseObservation(
        id=uuid4(),
        patient_id=uuid4(),
        taken_at=datetime(2026, 9, 13, 8, 30, 0, tzinfo=timezone.utc),
        value=GlucoseValue(145),
        tag=ReadingTag("fasting"),
        confirmation=PatientConfirmationState.CONFIRMED,
        confirmed_by=PhoneNumber("+919876543210"),
        created_at=datetime(2026, 9, 13, 8, 31, 0, tzinfo=timezone.utc),
    )

    model = glucose_observation_to_model(obs, tenant_id)
    assert model.tenant_id == tenant_id
    assert model.value_mg_dl == 145
    assert model.tag == "fasting"
    assert model.confirmation == "confirmed"

    restored = glucose_observation_to_domain(model)
    assert restored.id == obs.id
    assert restored.patient_id == obs.patient_id
    assert restored.value is not None
    assert restored.value.value_mg_dl == 145
    assert restored.tag == ReadingTag("fasting")
    assert restored.confirmation == PatientConfirmationState.CONFIRMED
    assert restored.confirmed_by is not None
    assert restored.confirmed_by.value == "+919876543210"


def test_meal_observation_mapping_roundtrip_with_portion_and_analytics():
    tenant_id = uuid4()
    portion = MealPortion(
        food_key="dal",
        katori=KatoriVolume(220),
        quantity=1.5,
    )
    obs = MealObservation(
        id=uuid4(),
        patient_id=uuid4(),
        recorded_at=datetime(2026, 9, 13, 13, 0, 0, tzinfo=timezone.utc),
        description="2 rotis and yellow dal",
        portion=portion,
        carbs_grams=45.0,
        glycemic_index="medium",
        confirmation=PatientConfirmationState.CONFIRMED,
        confirmed_by=PhoneNumber("+919876543210"),
        created_at=datetime(2026, 9, 13, 13, 5, 0, tzinfo=timezone.utc),
    )

    model = meal_observation_to_model(obs, tenant_id)
    assert model.portion_food_key == "dal"
    assert model.portion_volume_ml == 220
    assert model.portion_quantity == 1.5
    assert model.carbs_grams == 45.0
    assert model.glycemic_index == "medium"

    restored = meal_observation_to_domain(model)
    assert restored.id == obs.id
    assert restored.portion is not None
    assert restored.portion.food_key == "dal"
    assert restored.portion.katori.volume_ml == 220
    assert restored.portion.katori.label == "medium"
    assert restored.portion.quantity == 1.5
    assert restored.carbs_grams == 45.0
    assert restored.glycemic_index == "medium"
    assert restored.confirmation == PatientConfirmationState.CONFIRMED


def test_medication_plan_mapping_roundtrip():
    tenant_id = uuid4()
    plan = MedicationPlan(
        id=uuid4(),
        patient_id=uuid4(),
        prescribed_by_user_id=uuid4(),
        prescribed_by_role=CareTeamRole.DOCTOR,
        medication="Metformin 500mg",
        instruction="Twice daily after meals",
        active=True,
        created_at=datetime(2026, 9, 13, 10, 0, 0, tzinfo=timezone.utc),
    )

    model = medication_plan_to_model(plan, tenant_id)
    assert model.prescribed_by_role == "doctor"
    assert model.medication == "Metformin 500mg"

    restored = medication_plan_to_domain(model)
    assert restored.id == plan.id
    assert restored.prescribed_by_role == CareTeamRole.DOCTOR
    assert restored.medication == "Metformin 500mg"
    assert restored.instruction == "Twice daily after meals"
    assert restored.active is True


def test_care_task_mapping_roundtrip():
    tenant_id = uuid4()
    task = CareTask(
        id=uuid4(),
        patient_id=uuid4(),
        assigned_to_user_id=uuid4(),
        description="Follow up on postprandial glucose spike",
        status=CareTaskStatus.IN_PROGRESS,
        created_at=datetime(2026, 9, 13, 9, 0, 0, tzinfo=timezone.utc),
    )

    model = care_task_to_model(task, tenant_id)
    assert model.status == "in_progress"

    restored = care_task_to_domain(model)
    assert restored.id == task.id
    assert restored.status == CareTaskStatus.IN_PROGRESS
    assert restored.description == task.description


def test_ai_review_artifact_mapping_roundtrip():
    tenant_id = uuid4()
    artifact = AIReviewArtifact(
        id=uuid4(),
        patient_id=uuid4(),
        artifact_kind="extracted_observation",
        authority=ReviewAuthority.CLINICIAN_REVIEW,
        state=ReviewState.PENDING_REVIEW,
        generated_by="gemini-1.5-pro",
        summary="Extracted 1 bowl of dal with 2 rotis",
        reviewed_by_user_id=None,
        created_at=datetime(2026, 9, 13, 14, 0, 0, tzinfo=timezone.utc),
    )

    model = ai_artifact_to_model(artifact, tenant_id)
    assert model.state == "pending_review"
    assert model.authority == "clinician_review"

    restored = ai_artifact_to_domain(model)
    assert restored.id == artifact.id
    assert restored.state == ReviewState.PENDING_REVIEW
    assert restored.authority == ReviewAuthority.CLINICIAN_REVIEW
    assert restored.summary == artifact.summary
