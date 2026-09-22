"""Unit tests for human-like conversational clinical intelligence in WhatsApp."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
import pytest

from backend.application.ops.contracts import DeliveryOutcome, OutboundMessage, OutboxJob
from backend.application.ops.handlers import WhatsAppIntakeHandler
from backend.application.ops.ports import ChannelSender
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.domain.entities import Patient
from backend.domain.value_objects import PhoneNumber, UHID
from tests.unit.ops.test_whatsapp_confirm_loop import (
    DummyClock,
    DummyIdGen,
    RecordingAuditStore,
    RecordingEventPublisher,
    RecordingSender,
    SimpleUow,
    FixedTenantResolver,
    _build_handler,
    _make_job,
)


def test_conversational_onboarding_question():
    patient_id = uuid4()
    tenant_id = uuid4()
    patient = Patient(id=patient_id, name="Subham Das", uh_id=UHID("UHID-123"), active=True)
    uow = SimpleUow(patient)
    sender = RecordingSender()
    audit_store = RecordingAuditStore()
    handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

    job = _make_job("Hi THALI, my WhatsApp is connected! How can I log my blood sugar?")
    outcome = handler.handle(job)
    assert outcome == DeliveryOutcome.SUCCESS

    assert len(sender.sent) == 1
    reply = sender.sent[0].template_params["body"]
    assert "Subham Das" in reply
    assert "Blood Sugar" in reply
    assert "118 fasting" in reply or "fasting" in reply


def test_conversational_glucose_clinical_interpretation():
    patient_id = uuid4()
    tenant_id = uuid4()
    patient = Patient(id=patient_id, name="Subham Das", uh_id=UHID("UHID-123"), active=True)
    uow = SimpleUow(patient)
    sender = RecordingSender()
    audit_store = RecordingAuditStore()
    handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

    # 1. Fasting 118 mg/dL
    job1 = _make_job("118 fasting")
    outcome1 = handler.handle(job1)
    assert outcome1 == DeliveryOutcome.SUCCESS
    obs1 = uow.glucose_observations.list_for_patient(patient_id)
    assert len(obs1) == 1
    assert obs1[0].value.value_mg_dl == 118

    reply1 = sender.sent[0].template_params["body"]
    assert "Subham Das" in reply1
    assert "118 mg/dl" in reply1.lower()
    assert "normal fasting target" in reply1.lower() or "70–130" in reply1

    # 2. Post lunch 142 mg/dL
    job2 = _make_job("142 post lunch")
    outcome2 = handler.handle(job2)
    assert outcome2 == DeliveryOutcome.SUCCESS
    obs2 = uow.glucose_observations.list_for_patient(patient_id)
    assert len(obs2) == 2
    assert obs2[1].value.value_mg_dl == 142

    reply2 = sender.sent[1].template_params["body"]
    assert "142 mg/dl" in reply2.lower()
    assert "post-meal target" in reply2.lower()


def test_conversational_meal_composition_prompt():
    patient_id = uuid4()
    tenant_id = uuid4()
    patient = Patient(id=patient_id, name="Subham Das", uh_id=UHID("UHID-123"), active=True)
    uow = SimpleUow(patient)
    sender = RecordingSender()
    audit_store = RecordingAuditStore()
    handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

    job = _make_job("2 roti and dal")
    outcome = handler.handle(job)
    assert outcome == DeliveryOutcome.SUCCESS

    meals = uow.meal_observations.list_for_patient(patient_id)
    assert len(meals) == 1
    assert "2 roti and dal" in meals[0].description

    reply = sender.sent[0].template_params["body"]
    assert "Subham Das" in reply
    assert "Plate Composition" in reply
    assert "Roti" in reply
    assert "Dal" in reply
    assert "confirm" in reply.lower()
    # Information asymmetry invariants
    assert "carb" not in reply.lower()
    assert "glycemic" not in reply.lower()


def test_conversational_symptom_safety():
    patient_id = uuid4()
    tenant_id = uuid4()
    patient = Patient(id=patient_id, name="Subham Das", uh_id=UHID("UHID-123"), active=True)
    uow = SimpleUow(patient)
    sender = RecordingSender()
    audit_store = RecordingAuditStore()
    handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

    job = _make_job("Mujhe thoda chakkar aa raha hai aur pasina ho raha hai")
    outcome = handler.handle(job)
    assert outcome == DeliveryOutcome.SUCCESS

    reply = sender.sent[0].template_params["body"]
    assert "Subham Das" in reply
    assert "Hypoglycemia" in reply or "low blood sugar" in reply.lower()
    assert "glucose" in reply.lower() or "shakkar" in reply.lower()


def test_conversational_diet_query():
    patient_id = uuid4()
    tenant_id = uuid4()
    patient = Patient(id=patient_id, name="Subham Das", uh_id=UHID("UHID-123"), active=True)
    uow = SimpleUow(patient)
    sender = RecordingSender()
    audit_store = RecordingAuditStore()
    handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

    job = _make_job("Kya main aam kha sakta hoon?")
    outcome = handler.handle(job)
    assert outcome == DeliveryOutcome.SUCCESS

    reply = sender.sent[0].template_params["body"]
    assert "Subham Das" in reply
    assert "ICMR" in reply
    assert "Aam" in reply or "Phal" in reply
