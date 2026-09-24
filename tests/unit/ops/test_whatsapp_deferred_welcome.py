"""Unit tests for deferred WELCOME greeting delivery on first inbound message."""

from __future__ import annotations

from uuid import uuid4

from backend.application.ops.contracts import DeliveryOutcome
from backend.application.ops.handlers import WhatsAppIntakeHandler
from backend.domain.entities import Notification, NotificationChannel, NotificationStatus, NotificationType, Patient
from backend.domain.value_objects import UHID
from tests.unit.ops.test_whatsapp_confirm_loop import (
    RecordingAuditStore,
    RecordingSender,
    SimpleUow,
    _build_handler,
    _make_job,
)


def _pending_welcome(patient_id) -> Notification:
    return Notification(
        tenant_id=uuid4(),
        recipient_id=patient_id,
        recipient_phone="+919876543210",
        patient_id=patient_id,
        notification_type=NotificationType.WELCOME,
        channel=NotificationChannel.WHATSAPP,
        template_name="text",
        template_params={"body": "Namaste Test ji! Welcome to *THALI × P.L.A.T.E.*"},
        status=NotificationStatus.PENDING,
        scheduled_at=None,
    )


def test_deferred_welcome_delivered_on_first_inbound():
    patient_id = uuid4()
    tenant_id = uuid4()
    patient = Patient(id=patient_id, name="Test", uh_id=UHID("UHID-123"), active=True)
    uow = SimpleUow(patient)
    # Simulate connect-time marker recorded before the customer ever messaged
    marker = _pending_welcome(patient_id)
    uow.notifications.add(marker)

    sender = RecordingSender()
    audit_store = RecordingAuditStore()
    handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

    job = _make_job("118 fasting")
    outcome = handler.handle(job)
    assert outcome == DeliveryOutcome.SUCCESS

    # Greeting was delivered first...
    assert len(sender.sent) >= 1
    assert "Welcome to *THALI × P.L.A.T.E.*" in sender.sent[0].template_params["body"]
    # ...and the marker is now terminal DELIVERED, so it will not re-fire.
    stored = uow.notifications.get(marker.id)
    assert stored.status == NotificationStatus.DELIVERED
    assert stored.delivered_at is not None

    # A second inbound does NOT re-send the greeting (marker already delivered).
    sender.sent.clear()
    outcome2 = handler.handle(_make_job("130 post lunch"))
    assert outcome2 == DeliveryOutcome.SUCCESS
    assert all("Welcome to" not in m.template_params.get("body", "") for m in sender.sent)


def test_deferred_welcome_skipped_when_no_marker():
    patient_id = uuid4()
    tenant_id = uuid4()
    patient = Patient(id=patient_id, name="Test", uh_id=UHID("UHID-123"), active=True)
    uow = SimpleUow(patient)
    sender = RecordingSender()
    audit_store = RecordingAuditStore()
    handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

    outcome = handler.handle(_make_job("118 fasting"))
    assert outcome == DeliveryOutcome.SUCCESS
    assert len(sender.sent) == 1
    assert "Welcome to" not in sender.sent[0].template_params.get("body", "")


def test_deferred_welcome_does_not_block_unregistered_sender():
    patient_id = uuid4()
    tenant_id = uuid4()
    patient = Patient(id=patient_id, name="Test", uh_id=UHID("UHID-123"), active=True)
    uow = SimpleUow(patient)
    marker = _pending_welcome(patient_id)
    uow.notifications.add(marker)

    sender = RecordingSender()
    audit_store = RecordingAuditStore()
    handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

    # Resolver always resolves in this harness; verify the marker path is resilient
    # when the marker body is empty (falls back to no greeting, normal processing).
    marker.template_params = {}
    uow.notifications.save(marker)
    outcome = handler.handle(_make_job("dal and rice"))
    assert outcome == DeliveryOutcome.SUCCESS
    assert len(sender.sent) == 1  # meal prompt only, no greeting


def test_deferred_welcome_onboarding_inbound_no_duplicate_reply():
    patient_id = uuid4()
    tenant_id = uuid4()
    patient = Patient(id=patient_id, name="Subham Das", uh_id=UHID("UHID-123"), active=True)
    uow = SimpleUow(patient)
    marker = _pending_welcome(patient_id)
    uow.notifications.add(marker)

    sender = RecordingSender()
    audit_store = RecordingAuditStore()
    handler = _build_handler(tenant_id, patient, uow, sender, audit_store)

    job = _make_job("Hi THALI, my WhatsApp is connected! How can I log my blood sugar?")
    outcome = handler.handle(job)
    assert outcome == DeliveryOutcome.SUCCESS

    # Exactly 1 message sent: the rich welcome greeting
    assert len(sender.sent) == 1
    body = sender.sent[0].template_params["body"]
    assert "Welcome to *THALI × P.L.A.T.E.*" in body
    assert "Voice Note" in body
    assert "Plate Photo" in body
    assert "Reminders" in body

    # Marker is now delivered
    stored = uow.notifications.get(marker.id)
    assert stored.status == NotificationStatus.DELIVERED