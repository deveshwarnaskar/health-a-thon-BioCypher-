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
from backend.domain.entities import MealObservation, Notification, NotificationStatus, Patient
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


class InMemoryNotificationRepo:
    def __init__(self):
        self.by_id: dict[UUID, Notification] = {}

    def add(self, notification: Notification) -> None:
        self.by_id[notification.id] = notification

    def get(self, notification_id: UUID) -> Notification:
        return self.by_id[notification_id]

    def save(self, notification: Notification) -> None:
        self.by_id[notification.id] = notification

    def list_for_patient(self, patient_id: UUID, limit: int = 50, offset: int = 0) -> list[Notification]:
        return [n for n in self.by_id.values() if n.patient_id == patient_id]

    def list_for_recipient(self, recipient_id: UUID, limit: int = 50, offset: int = 0) -> list[Notification]:
        return [n for n in self.by_id.values() if n.recipient_id == recipient_id]

    def list_for_tenant(self, status: NotificationStatus | None = None, limit: int = 50, offset: int = 0) -> list[Notification]:
        return list(self.by_id.values())

    def list_due(self, before: datetime, limit: int = 50) -> list[Notification]:
        return []


class SimpleUow(UnitOfWork):
    def __init__(self, patient: Patient):
        self.patients = InMemoryPatientRepo(patient)
        self.meal_observations = InMemoryMealRepo()
        self.glucose_observations = InMemoryGlucoseRepo()
        self.notifications = InMemoryNotificationRepo()
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


def _make_job(text: str, phone: str = "+919876543210", interactive_reply_id: str | None = None) -> OutboxJob:
    payload = {"source_phone": phone, "text": text, "message_id": "msg-123"}
    if interactive_reply_id is not None:
        payload["interactive_reply_id"] = interactive_reply_id
    return OutboxJob(
        event_id=uuid4(),
        event_type="whatsapp.message.received",
        tenant_id=UUID(int=1),
        patient_id=UUID(int=2),
        correlation_id=uuid4(),
        payload=payload,
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

    def test_unsupported_intent_blocked_with_guidance(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        job = _make_job("can you write a poem about the sunrise?")
        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        # Verify no clinical observations were created
        assert len(uow.glucose_observations.list_for_patient(patient_id)) == 0
        assert len(uow.meal_observations.list_for_patient(patient_id)) == 0

        # Verify polite health assistant guidance was sent
        assert len(sender.sent) == 1
        reply = sender.sent[0].template_params["body"]
        assert "health assistant" in reply.lower()
        assert "glucose" in reply.lower()

    def test_help_intent_returns_instructions(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        job = _make_job("help")
        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        assert len(sender.sent) == 1
        reply = sender.sent[0].template_params["body"]
        assert "sugar darz karein" in reply.lower() or "assistant" in reply.lower()

    def test_cancel_intent_cancels_pending_meal(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        # 1. Log a meal draft
        handler.handle(_make_job("2 roti and dal"))
        meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(meals) == 1
        assert meals[0].confirmation == PatientConfirmationState.PENDING

        # 2. Patient sends "cancel"
        job_cancel = _make_job("cancel")
        outcome = handler.handle(job_cancel)
        assert outcome == DeliveryOutcome.SUCCESS

        # Verify meal is rejected/cancelled
        assert meals[0].confirmation == PatientConfirmationState.REJECTED
        assert len(sender.sent) == 2
        cancel_reply = sender.sent[1].template_params["body"]
        assert "cancel" in cancel_reply.lower()

    def test_status_intent_returns_latest_glucose(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        # 1. Log glucose reading
        handler.handle(_make_job("135 fasting"))
        assert len(uow.glucose_observations.list_for_patient(patient_id)) == 1

        # 2. Patient asks for status
        job_status = _make_job("status")
        outcome = handler.handle(job_status)
        assert outcome == DeliveryOutcome.SUCCESS

        assert len(sender.sent) == 2
        status_reply = sender.sent[1].template_params["body"]
        assert "135 mg/dl" in status_reply.lower()

    def test_glucose_stated_time_sets_taken_at(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        # Message with stated time: "aaj subah 8 am 142"
        job = _make_job("aaj subah 8 am 142")
        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        obs = uow.glucose_observations.list_for_patient(patient_id)
        assert len(obs) == 1
        assert obs[0].value.value_mg_dl == 142
        assert obs[0].taken_at.hour == 8
        assert obs[0].taken_at.minute == 0

    def test_unknown_sender_sends_guidance_and_fails_permanently(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()

        class NoneResolver(ChannelTenantResolver):
            def resolve(self, phone: str):
                return None

        handler = WhatsAppIntakeHandler(
            tenant_resolver=NoneResolver(),
            uow_factory=lambda _: uow,
            events_factory=lambda _: RecordingEventPublisher(),
            audit_factory=lambda _: audit_store,
            clock=DummyClock(),
            id_gen=DummyIdGen(),
            sender=sender,
        )

        from backend.application.ops.errors import PermanentWorkerFailure

        job = _make_job("140 fasting", phone="+919999999999")
        with pytest.raises(PermanentWorkerFailure):
            handler.handle(job)

        # Verify polite unregistered guidance was sent to the unknown sender
        assert len(sender.sent) == 1
        assert "registered nahi hai" in sender.sent[0].template_params["body"].lower()

    def test_interactive_button_confirm_yes(self):
        """Button click with interactive_reply_id='confirm_yes' confirms the pending meal."""
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        # 1. Draft meal
        handler.handle(_make_job("2 roti and dal"))
        meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(meals) == 1
        assert meals[0].confirmation == PatientConfirmationState.PENDING

        # 2. User clicks "Yes / Haan" button
        job_btn = _make_job("Yes / Haan", interactive_reply_id="confirm_yes")
        outcome = handler.handle(job_btn)
        assert outcome == DeliveryOutcome.SUCCESS

        # Verify meal is confirmed, not drafted again!
        confirmed_meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(confirmed_meals) == 1
        assert confirmed_meals[0].confirmation == PatientConfirmationState.CONFIRMED
        ack = sender.sent[1].template_params["body"]
        assert "record ho gaya" in ack.lower()
        assert "2 roti and dal" in ack

    def test_free_text_yes_slash_haan_confirms_meal(self):
        """Typing 'Yes / Haan' without button id still confirms the pending meal."""
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        handler.handle(_make_job("2 roti and dal"))
        job_text = _make_job("Yes / Haan")
        outcome = handler.handle(job_text)
        assert outcome == DeliveryOutcome.SUCCESS

        meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(meals) == 1
        assert meals[0].confirmation == PatientConfirmationState.CONFIRMED

    def test_free_text_yes_small_updates_portion_to_small(self):
        """Typing 'Yes small' confirms the meal AND updates portion to Small (150 ml)."""
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        handler.handle(_make_job("2 roti and dal"))
        job_portion = _make_job("Yes small")
        outcome = handler.handle(job_portion)
        assert outcome == DeliveryOutcome.SUCCESS

        meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(meals) == 1
        assert meals[0].confirmation in (PatientConfirmationState.CONFIRMED, PatientConfirmationState.CORRECTED)
        assert meals[0].portion is not None
        assert meals[0].portion.katori.volume_ml == 150
        ack = sender.sent[1].template_params["body"]
        assert "small" in ack.lower()
        assert "record ho gaya" in ack.lower()

    def test_interactive_button_confirm_cancel(self):
        """Button click with interactive_reply_id='confirm_cancel' cancels the pending meal."""
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        handler.handle(_make_job("2 roti and dal"))
        job_cancel = _make_job("Cancel / Radd", interactive_reply_id="confirm_cancel")
        outcome = handler.handle(job_cancel)
        assert outcome == DeliveryOutcome.SUCCESS

        meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(meals) == 1
        assert meals[0].confirmation == PatientConfirmationState.REJECTED
        ack = sender.sent[1].template_params["body"]
        assert "cancel" in ack.lower()

    def test_free_text_cancel_slash_radd(self):
        """Typing 'Cancel / Radd' rejects the pending meal draft."""
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        handler.handle(_make_job("2 roti and dal"))
        job_cancel = _make_job("Cancel / Radd")
        outcome = handler.handle(job_cancel)
        assert outcome == DeliveryOutcome.SUCCESS

        meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(meals) == 1
        assert meals[0].confirmation == PatientConfirmationState.REJECTED

    def test_yes_without_pending_meal_does_not_create_draft(self):
        """Typing 'YES' or 'Haan' when no meal is pending does NOT create a meal draft."""
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sita", uh_id=UHID("UHID-123"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

        job_orphan = _make_job("YES")
        outcome = handler.handle(job_orphan)
        assert outcome == DeliveryOutcome.SUCCESS

        # Absolutely NO meal draft was created!
        meals = uow.meal_observations.list_for_patient(patient_id)
        assert len(meals) == 0
        ack = sender.sent[0].template_params["body"]
        assert "koi pending meal record nahi mila" in ack.lower()

    def test_scientific_quantity_meal_calculation(self):
        """Scientific nutrition parser calculates multi-item quantities and composite GI."""
        from backend.infrastructure.parsing.nutrition_taxonomy import classify_text, estimate_nutrition

        # "2 roti and dal"
        items = classify_text("2 roti and dal")
        assert len(items) == 2
        roti_item = next(i for i in items if i["item"] == "roti")
        dal_item = next(i for i in items if i["item"] == "dal")
        assert roti_item["quantity"] == 2.0
        assert dal_item["quantity"] == 1.0

        est_med = estimate_nutrition(items, portion="m")
        # 2 roti at 220ml = 95.0g carbs; 1 dal at 220ml = 29.7g carbs -> total 124.7g
        assert est_med.carbs_grams == 124.7
        # Composite GI: (95.0*58 + 29.7*35)/124.7 = 52.5 -> "low"
        assert est_med.gi_category == "low"

        # Portion Small (150ml)
        est_small = estimate_nutrition(items, portion="s")
        assert est_small.carbs_grams < est_med.carbs_grams
        assert est_small.carbs_grams == round(24.0 * 150 * 2.0 * 0.009 + 15.0 * 150 * 1.0 * 0.009, 1)

