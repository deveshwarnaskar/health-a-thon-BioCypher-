"""Gate 04 — event identity/provenance survives application flow, and
deterministic time/identifiers are injected through ports."""

from uuid import uuid4

from backend.application.commands import CreateCareTask, IngestGlucoseReading, LogMealDraft
from backend.domain.events import (
    CareTaskCreated,
    GlucoseObservationRecorded,
    MealObservationRecorded,
)
from backend.domain.value_objects import GlucoseValue, KatoriVolume, MealPortion
from tests.unit.application.fakes import (
    FakeClock,
    FakeEventPublisher,
    FakeIdGenerator,
    InMemoryUnitOfWork,
    seed_member,
    seed_patient,
)
from backend.application.services import (
    CreateCareTaskHandler,
    IngestGlucoseHandler,
    LogMealDraftHandler,
)
from backend.domain.entities import CareTeamRole
from datetime import datetime, timezone

NOW = datetime(2026, 9, 1, 7, 30, tzinfo=timezone.utc)


def test_event_carries_entity_provenance_and_correlation(world):
    app, events, patient_id = world["app"], world["events"], world["patient_id"]
    cid = uuid4()

    result = app.ingest_glucose.handle(
        IngestGlucoseReading(patient_id=patient_id, value=GlucoseValue(140), taken_at=NOW, correlation_id=cid)
    )

    event = events.published[-1]
    assert isinstance(event, GlucoseObservationRecorded)
    assert event.event_type == "glucose_observation.recorded"
    assert event.patient_id == patient_id
    assert event.correlation_id == cid
    assert event.observation_id == result.observation_id
    assert event.event_id != result.observation_id
    assert event.occurred_at == world["clock"].now()


def test_correlation_propagates_from_command(world):
    app, events, patient_id = world["app"], world["events"], world["patient_id"]
    cid = uuid4()
    result = app.create_care_task.handle(
        CreateCareTask(
            patient_id=patient_id,
            assigned_to_user_id=world["nurse_user_id"],
            description="Follow-up",
            correlation_id=cid,
        )
    )
    event = events.published[-1]
    assert isinstance(event, CareTaskCreated)
    assert event.correlation_id == cid
    assert event.care_task_id == result.care_task_id


def test_deterministic_time_and_identifiers(world):
    uow = InMemoryUnitOfWork()
    events = FakeEventPublisher()
    clock = FakeClock(NOW)
    id_gen = FakeIdGenerator(seed=555)
    handler = IngestGlucoseHandler(uow, events, clock, id_gen)
    seed_patient(uow, world["patient_id"])
    uow.commit()

    a = handler.handle(
        IngestGlucoseReading(patient_id=world["patient_id"], value=GlucoseValue(140), taken_at=NOW)
    )
    event_a = events.published[-1]

    uow2 = InMemoryUnitOfWork()
    events2 = FakeEventPublisher()
    clock2 = FakeClock(NOW)
    id_gen2 = FakeIdGenerator(seed=555)
    handler2 = IngestGlucoseHandler(uow2, events2, clock2, id_gen2)
    seed_patient(uow2, world["patient_id"])
    uow2.commit()

    b = handler2.handle(
        IngestGlucoseReading(patient_id=world["patient_id"], value=GlucoseValue(140), taken_at=NOW)
    )
    event_b = events2.published[-1]

    assert a == b
    assert event_a == event_b
    assert a.observation_id == event_a.observation_id


def test_deterministic_meal_draft_uses_injected_clock_and_id():
    uow = InMemoryUnitOfWork()
    events = FakeEventPublisher()
    clock = FakeClock(NOW)
    id_gen = FakeIdGenerator(seed=7)
    handler = LogMealDraftHandler(uow, events, clock, id_gen)
    seed_patient(uow, uuid4())
    uow.commit()
    patient_id = list(uow.patients.list())[0].id
    portion = MealPortion(food_key="dal", katori=KatoriVolume(220), quantity=1.0)

    result = handler.handle(
        LogMealDraft(patient_id=patient_id, description="dal", recorded_at=NOW, portion=portion)
    )
    event = events.published[-1]

    assert isinstance(event, MealObservationRecorded)
    stored = uow.meal_observations.get(result.meal_observation_id)
    assert stored.created_at == NOW
    assert event.occurred_at == NOW
    assert stored.id == event.observation_id


def test_ids_are_sequential_and_unique(world):
    id_gen = world["id_gen"]
    first = id_gen.new_uuid()
    second = id_gen.new_uuid()
    assert first != second
    assert int(first) + 1 == int(second)