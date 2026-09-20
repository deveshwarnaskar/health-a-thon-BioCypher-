"""Unit tests for WhatsApp confirm loop and information asymmetry in ops handlers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.application.ops.contracts import (
    AuditAction,
    DeliveryOutcome,
    DeliveryResult,
    OutboundMessage,
    OutboxJob,
    ResolvedChannelPatient,
)
from backend.application.ops.handlers import WhatsAppIntakeHandler
from backend.application.ops.ports import ChannelSender, ChannelTenantResolver
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.domain.entities import MealObservation, Patient
from backend.domain.value_objects import (
    KatoriVolume,
    MealPortion,
    PatientConfirmationState,
    PhoneNumber,
    UHID,
)


class DummyClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)


class DummyIdGen(IdGenerator):
    def __init__(self):
        self._counter = 0

    def new_uuid(self) -> UUID:
        self._counter += 1
        return UUID(int=self._counter)


class RecordingSender(ChannelSender):
    def __init__(self):
        self.sent: list[OutboundMessage] = []

    def send(self, message: OutboundMessage) -> DeliveryResult:
        self.sent.append(message)
        return DeliveryResult(success=True, provider_delivery_id=str(uuid4()))


class RecordingAuditStore:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


class RecordingEventPublisher(DomainEventPublisher):
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)


class InMemoryMealRepo:
    def __init__(self):
        self.by_id: dict[UUID, MealObservation] = {}

    def add(self, meal: MealObservation) -> None:
        self.by_id[meal.id] = meal

    def get(self, meal_id: UUID) -> MealObservation:
        return self.by_id[meal_id]

    def save(self, meal: MealObservation) -> None:
        self.by_id[meal.id] = meal

    def list_for_patient(self, patient_id: UUID) -> list[MealObservation]:
        return [m for m in self.by_id.values() if m.patient_id == patient_id]


class InMemoryGlucoseRepo:
    def __init__(self):
        self.by_id = {}

    def add(self, obs):
        self.by_id[obs.id] = obs

    def get(self, obs_id):
        return self.by_id[obs_id]

    def list_for_patient(self, patient_id):
        return [o for o in self.by_id.values() if o.patient_id == patient_id]


class InMemoryPatientRepo:
    def __init__(self, patient: Patient):
        self.patient = patient

    def get(self, patient_id: UUID) -> Patient:
        return self.patient


class SimpleUow(UnitOfWork):
    def __init__(self, patient: Patient):
        self.patients = InMemoryPatientRepo(patient)
        self.meal_observations = InMemoryMealRepo()
        self.glucose_observations = InMemoryGlucoseRepo()
        self.committed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


class FixedTenantResolver(ChannelTenantResolver):
    def __init__(self, tenant_id: UUID, patient_id: UUID):
        self.tenant_id = tenant_id
        self.patient_id = patient_id

    def resolve(self, phone: str) -> ResolvedChannelPatient | None:
        return ResolvedChannelPatient(
            tenant_id=self.tenant_id,
            patient_id=self.patient_id,
        )


def _build_handler(tenant_id: UUID, patient: Patient, uow: SimpleUow, sender: RecordingSender, audit_store: RecordingAuditStore):
    return WhatsAppIntakeHandler(
        tenant_resolver=FixedTenantResolver(tenant_id, patient.id),
        uow_factory=lambda _: uow,
        events_factory=lambda _: RecordingEventPublisher(),
        audit_factory=lambda _: audit_store,
        clock=DummyClock(),
        id_gen=DummyIdGen(),
        sender=sender,
    )


def _make_job(text: str, phone: str = "+919876543210") -> OutboxJob:
    return OutboxJob(
        event_id=uuid4(),
        event_type="whatsapp.message.received",
        tenant_id=UUID(int=1),
        patient_id=UUID(int=2),
        correlation_id=uuid4(),
        payload={"source_phone": phone, "text": text, "message_id": "msg-123"},
        occurred_at=datetime.now(timezone.utc),
        retry_count=0,
    )


class TestWhatsAppConfirmLoop:
    def test_meal_draft_followed_by_confirmation(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        # 1. Patient logs meal draft
        job1 = _make_job("dal and rice")
        outcome1 = handler.handle(job1)
        assert outcome1 == DeliveryOutcome.SUCCESS

        # Verify draft was logged in pending state
        meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(meals) == 1
        assert meals[0].confirmation == PatientConfirmationState.PENDING
        assert len(sender.sent) == 1
        prompt = sender.sent[0].template_params["body"]
        assert "confirm" in prompt.lower()
        # Verify NO carbs or GI in patient prompt
        assert "carb" not in prompt.lower()
        assert "glycemic" not in prompt.lower()

        # 2. Patient confirms with "YES"
        job2 = _make_job("YES")
        outcome2 = handler.handle(job2)
        assert outcome2 == DeliveryOutcome.SUCCESS

        # Verify meal is now CONFIRMED
        confirmed_meal = uow.meal_observations.get(meals[0].id)
        assert confirmed_meal.confirmation == PatientConfirmationState.CONFIRMED
        assert len(sender.sent) == 2
        ack = sender.sent[1].template_params["body"]
        assert "record ho gaya" in ack.lower()
        # Strictly no carbs/GI exposed to patient
        assert "carb" not in ack.lower()
        assert "glycemic" not in ack.lower()

    def test_meal_correction_with_portion_adjustment(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        # 1. Patient logs meal
        handler.handle(_make_job("roti and sabzi"))
        meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(meals) == 1

        # 2. Patient adjusts portion to small: "correct s"
        job_correct = _make_job("correct s")
        outcome = handler.handle(job_correct)
        assert outcome == DeliveryOutcome.SUCCESS

        # Verify meal portion updated to Small (150 ml)
        meal = uow.meal_observations.get(meals[0].id)
        assert meal.portion is not None
        assert meal.portion.katori.volume_ml == 150
        assert meal.confirmation in (PatientConfirmationState.CONFIRMED, PatientConfirmationState.CORRECTED)

    def test_ambiguous_reading_triggers_clarification_prompt(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        # Ambiguous message
        job = _make_job("shayad 230 ya 330")
        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        # No glucose reading should have been saved
        assert len(uow.glucose_observations.list_for_patient(patient_id)) == 0
        # Clarification prompt sent
        assert len(sender.sent) == 1
        reply = sender.sent[0].template_params["body"]
        assert "clear nahi hai" in reply.lower()

    def test_glucose_reading_ingest_and_acknowledgment(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        job = _make_job("140 fasting")
        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        # Glucose reading recorded
        obs = uow.glucose_observations.list_for_patient(patient_id)
        assert len(obs) == 1
        assert obs[0].value.value_mg_dl == 140
        assert len(sender.sent) == 1
        reply = sender.sent[0].template_params["body"]
        assert "140 mg/dl" in reply.lower()
