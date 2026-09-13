"""Gate 04 — successful command orchestration: domain behavior, repository
interaction, and event publication through the outbound ports."""

from datetime import datetime, timezone

import pytest

from backend.application.commands import (
    CompleteCareTask,
    ConfirmMealObservation,
    CreateCareTask,
    LogMealDraft,
    LinkPatientPhone,
    ReviewAIArtifact,
    ReviewDecision,
)
from backend.application.commands import (
    CreateMedicationPlan,
    GenerateAIReviewArtifact,
    IngestGlucoseReading,
    RecordMedicationAdministration,
)
from backend.domain.events import (
    AIArtifactGenerated,
    AIArtifactReviewed,
    CareTaskCompleted,
    CareTaskCreated,
    GlucoseObservationRecorded,
    MealObservationConfirmed,
    MealObservationRecorded,
    MedicationAdministrationRecorded,
)
from backend.domain.value_objects import (
    GlucoseValue,
    KatoriVolume,
    MealPortion,
    PhoneNumber,
    ReadingTag,
)

NOW = datetime(2026, 9, 1, 7, 30, tzinfo=timezone.utc)


def test_ingest_glucose_orchestrates_domain_repository_and_event(world):
    uow, events, app, patient_id = (
        world["uow"],
        world["events"],
        world["app"],
        world["patient_id"],
    )
    result = app.ingest_glucose.handle(
        IngestGlucoseReading(patient_id=patient_id, value=GlucoseValue(140), taken_at=NOW, tag=ReadingTag.FASTING)
    )

    assert result.value_mg_dl == 140
    stored = uow.glucose_observations.list_for_patient(patient_id)
    assert len(stored) == 1
    assert stored[0].id == result.observation_id
    assert stored[0].value == GlucoseValue(140)
    assert stored[0].tag is ReadingTag.FASTING
    assert uow.commits == 1

    event = events.published[-1]
    assert isinstance(event, GlucoseObservationRecorded)
    assert event.observation_id == result.observation_id
    assert event.patient_id == patient_id


def test_link_patient_phone_saves_through_port(world):
    uow, app, patient_id = world["uow"], world["app"], world["patient_id"]
    result = app.link_patient_phone.handle(
        LinkPatientPhone(patient_id=patient_id, phone=PhoneNumber("+91 90000 00009"))
    )

    assert result.phone_masked == "+********0009"
    stored = uow.patients.get(patient_id)
    assert stored.phone.digits == "919000000009"
    assert uow.commits == 1


def test_log_meal_draft_creates_pending_observation(world):
    uow, events, app, patient_id = world["uow"], world["events"], world["app"], world["patient_id"]
    portion = MealPortion(food_key="dal", katori=KatoriVolume(220), quantity=1.0)
    result = app.log_meal_draft.handle(
        LogMealDraft(patient_id=patient_id, description="1 katori dal", recorded_at=NOW, portion=portion)
    )

    stored = uow.meal_observations.get(result.meal_observation_id)
    assert stored.description == "1 katori dal"
    assert stored.portion == portion
    assert stored.confirmation.value == "pending"
    assert uow.commits == 1

    event = events.published[-1]
    assert isinstance(event, MealObservationRecorded)
    assert event.observation_id == result.meal_observation_id


def test_confirm_meal_observation_applies_domain_confirm(world):
    uow, events, app, patient_id = world["uow"], world["events"], world["app"], world["patient_id"]
    draft = app.log_meal_draft.handle(
        LogMealDraft(patient_id=patient_id, description="1 katori dal", recorded_at=NOW)
    )
    result = app.confirm_meal_observation.handle(
        ConfirmMealObservation(
            meal_observation_id=draft.meal_observation_id,
            confirmed_by=PhoneNumber("+919000000001"),
        )
    )

    assert result.confirmation == "confirmed"
    stored = uow.meal_observations.get(draft.meal_observation_id)
    assert stored.confirmation.value == "confirmed"
    assert uow.commits == 2

    event = events.published[-1]
    assert isinstance(event, MealObservationConfirmed)
    assert event.observation_id == draft.meal_observation_id


def test_record_medication_administration_publishes_event_without_mutating_plan(world):
    uow, events, app = world["uow"], world["events"], world["app"]
    plan_result = app.create_medication_plan.handle(
        CreateMedicationPlan(
            patient_id=world["patient_id"],
            prescribed_by_user_id=world["doctor_user_id"],
            medication="Metformin 500 mg",
            instruction="One tablet after dinner",
        )
    )
    original = uow.medication_plans.get(plan_result.medication_plan_id)

    result = app.record_medication_administration.handle(
        RecordMedicationAdministration(
            medication_plan_id=plan_result.medication_plan_id,
            administered_at=NOW,
            recorded_by=PhoneNumber("+919000000001"),
        )
    )

    assert result.medication_plan_id == plan_result.medication_plan_id
    after = uow.medication_plans.get(plan_result.medication_plan_id)
    assert after.instruction == original.instruction
    assert after.active is True

    event = events.published[-1]
    assert isinstance(event, MedicationAdministrationRecorded)
    assert event.medication_plan_id == plan_result.medication_plan_id
    assert event.patient_id == world["patient_id"]


def test_create_and_complete_care_task(world):
    uow, events, app, patient_id = world["uow"], world["events"], world["app"], world["patient_id"]
    created = app.create_care_task.handle(
        CreateCareTask(
            patient_id=patient_id,
            assigned_to_user_id=world["nurse_user_id"],
            description="Remind about evening dose",
        )
    )
    assert created.status == "open"
    assert uow.commits == 1
    assert isinstance(events.published[-1], CareTaskCreated)

    completed = app.complete_care_task.handle(CompleteCareTask(care_task_id=created.care_task_id))
    assert completed.status == "completed"
    assert uow.commits == 2
    assert isinstance(events.published[-1], CareTaskCompleted)

    stored = uow.care_tasks.get(created.care_task_id)
    assert stored.status.value == "completed"


def test_invalid_state_transition_propagates_and_rolls_back(world):
    from backend.domain.exceptions import InvalidStateTransition

    uow, app, patient_id = world["uow"], world["app"], world["patient_id"]
    created = app.create_care_task.handle(
        CreateCareTask(
            patient_id=patient_id,
            assigned_to_user_id=world["nurse_user_id"],
            description="Remind about evening dose",
        )
    )
    app.complete_care_task.handle(CompleteCareTask(care_task_id=created.care_task_id))
    commits_before = uow.commits

    with pytest.raises(InvalidStateTransition):
        app.complete_care_task.handle(CompleteCareTask(care_task_id=created.care_task_id))

    assert uow.rollbacks == 1
    assert uow.commits == commits_before


def test_ai_generation_produces_pending_review_artifact(world):
    uow, events, app, patient_id = world["uow"], world["events"], world["app"], world["patient_id"]
    result = app.generate_ai_artifact.handle(
        GenerateAIReviewArtifact(
            patient_id=patient_id,
            artifact_kind="glucose_summary",
            context="readings over the window",
        )
    )

    assert result.state == "pending_review"
    stored = uow.ai_artifacts.get(result.artifact_id)
    assert stored.state.value == "pending_review"
    assert stored.summary == world["ai"].summary
    assert uow.commits == 1
    assert isinstance(events.published[-1], AIArtifactGenerated)


def test_clinician_review_approves_artifact(world):
    app, patient_id = world["app"], world["patient_id"]
    generated = app.generate_ai_artifact.handle(
        GenerateAIReviewArtifact(patient_id=patient_id, artifact_kind="summary", context="data")
    )
    reviewed = app.review_ai_artifact.handle(
        ReviewAIArtifact(
            artifact_id=generated.artifact_id,
            reviewer_user_id=world["doctor_user_id"],
            decision=ReviewDecision.APPROVE,
        )
    )

    assert reviewed.state == "approved"
    assert reviewed.reviewed_by_user_id == world["doctor_user_id"]
    assert isinstance(world["events"].published[-1], AIArtifactReviewed)


def test_domain_invariant_glucose_boundary_rejects_at_input_shape(world):
    from backend.domain.exceptions import InvalidGlucoseValue

    with pytest.raises(InvalidGlucoseValue):
        IngestGlucoseReading(
            patient_id=world["patient_id"], value=GlucoseValue(19), taken_at=NOW
        )