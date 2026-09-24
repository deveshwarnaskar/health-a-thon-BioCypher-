"""Gate 04 — transaction boundary behaviour (UnitOfWork, no partial commits)."""

from datetime import datetime, timezone

import pytest

from backend.application.commands import (
    GenerateAIReviewArtifact,
    IngestGlucoseReading,
)
from backend.application.services import (
    GenerateAIReviewArtifactHandler,
    IngestGlucoseHandler,
)
from backend.domain.entities import GlucoseObservation
from backend.domain.value_objects import GlucoseValue
from tests.unit.application.conftest import PATIENT_ID
from tests.unit.application.fakes import (
    ExplodingEventPublisher,
    FailingAIArtifactGenerator,
    FakeClock,
    FakeEventPublisher,
    FakeIdGenerator,
    InMemoryCareTeamMemberStore,
    InMemoryUnitOfWork,
    seed_patient,
)

NOW = datetime(2026, 9, 1, 7, 30, tzinfo=timezone.utc)


def _obs():
    return GlucoseObservation(patient_id=PATIENT_ID, value=GlucoseValue(120), taken_at=NOW)


def test_commit_persists_all_repository_writes_atomically():
    uow = InMemoryUnitOfWork()
    seed_patient(uow, PATIENT_ID)
    uow.glucose_observations.add(_obs())

    uow.commit()

    assert uow.commits == 1
    assert len(uow.glucose_observations.list_for_patient(PATIENT_ID)) == 1


def test_rollback_discards_staged_writes():
    uow = InMemoryUnitOfWork()
    seed_patient(uow, PATIENT_ID)
    uow.commit()

    uow.glucose_observations.add(_obs())

    uow.rollback()

    assert uow.rollbacks == 1
    assert uow.glucose_observations.list_for_patient(PATIENT_ID) == []
    assert uow.patients.get(PATIENT_ID).id == PATIENT_ID


def test_handler_rolls_back_when_publisher_fails_after_staged_write(world):
    uow = world["uow"]
    handler = IngestGlucoseHandler(uow, ExplodingEventPublisher(), FakeClock(), FakeIdGenerator())

    with pytest.raises(RuntimeError):
        handler.handle(
            IngestGlucoseReading(patient_id=world["patient_id"], value=GlucoseValue(140), taken_at=NOW)
        )

    assert uow.commits == 0
    assert uow.rollbacks == 1
    assert uow.glucose_observations.list_for_patient(world["patient_id"]) == []


def test_handler_rolls_back_when_ai_provider_fails(world):
    uow = world["uow"]
    failing_ai = FailingAIArtifactGenerator()
    handler = GenerateAIReviewArtifactHandler(
        uow, FakeEventPublisher(), failing_ai, FakeClock(), FakeIdGenerator()
    )

    with pytest.raises(RuntimeError):
        handler.handle(
            GenerateAIReviewArtifact(
                patient_id=world["patient_id"],
                artifact_kind="summary",
                context="data",
            )
        )

    assert uow.commits == 0
    assert uow.rollbacks == 1
    assert uow.ai_artifacts.list_for_patient(world["patient_id"]) == []


def test_fakes_are_structural_ports():
    """Fakes satisfy the UnitOfWork and repository protocols structurally."""
    from backend.application.ports.repositories import (
        CareTaskRepository,
        GlucoseObservationRepository,
        MealObservationRepository,
        MedicationPlanRepository,
        PatientRepository,
    )
    from backend.application.ports.unit_of_work import UnitOfWork

    uow = InMemoryUnitOfWork()
    assert isinstance(uow, UnitOfWork)
    assert isinstance(uow.patients, PatientRepository)
    assert isinstance(uow.glucose_observations, GlucoseObservationRepository)
    assert isinstance(uow.meal_observations, MealObservationRepository)
    assert isinstance(uow.medication_plans, MedicationPlanRepository)
    assert isinstance(uow.care_tasks, CareTaskRepository)
    assert isinstance(uow.care_team_members, InMemoryCareTeamMemberStore)