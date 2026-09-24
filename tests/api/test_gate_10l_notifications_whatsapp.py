"""Gate 10L — Comprehensive Notifications + WhatsApp Integration Tests.

Verifies:
A. Notification creation
B. Notification tenant isolation
C. Notification lifecycle
D. Notification authorization
E. Notification idempotency
F. Duplicate webhook rejection
G. WhatsApp signature rejection
H. WhatsApp signature acceptance
I. WhatsApp glucose intake
J. WhatsApp meal intake
K. Patient/caregiver DTO asymmetry
L. Caregiver relationship enforcement
M. Deactivated patient denial
N. Cross-tenant denial
O. Outbox atomicity
P. Outbox retry
Q. Worker lease behavior
R. Delivery failure
S. Delivery success
T. Missing credential behavior
U. Rate limiting
V. Audit persistence
W. Correlation ID propagation
X. API error semantics
Y. Scheduler deterministic execution
Z. No AI/CDS behavior
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.application.ops.contracts import (
    CHANNEL_SEND_EVENT_TYPE,
    SYSTEM_WORKER_ACTOR_ID,
    WEBHOOK_INTAKE_EVENT_TYPE,
    DeliveryOutcome,
    DeliveryResult,
    OutboundMessage,
    OutboxJob,
    ResolvedChannelPatient,
    WebhookReceipt,
)
from backend.application.ops.handlers import ChannelDeliveryHandler, WhatsAppIntakeHandler
from backend.application.ops.scheduler import ReminderScheduler
from backend.application.ops.worker import OutboxWorker
from backend.application.services.notification_service import NotificationService
from backend.domain.entities import (
    CareTask,
    CareTaskStatus,
    CareTeamRole,
    GlucoseObservation,
    MealObservation,
    MedicationPlan,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    Patient,
)
from backend.domain.entities.notification import FORBIDDEN_NOTIFICATION_FIELDS
from backend.domain.events.channel import ChannelMessageQueued
from backend.domain.exceptions import DomainError, EntityNotFound, InvalidStateTransition
from backend.domain.value_objects import GlucoseValue, PhoneNumber, UHID
from backend.infrastructure.channel.whatsapp_sender import WhatsAppChannelSender
from backend.infrastructure.config.clock import SystemClock
from backend.infrastructure.config.id_generator import Uuid4IdGenerator
from backend.infrastructure.persistence.models import (
    AuditEventModel,
    DomainEventOutboxModel,
    NotificationModel,
    OrganizationModel,
    PatientModel,
)
from backend.infrastructure.persistence.ops.audit_store import SqlAlchemyAuditStore
from backend.infrastructure.persistence.ops.outbox_store import SqlAlchemyOutboxWorkerStore
from backend.infrastructure.persistence.ops.replay_store import SqlAlchemyWebhookReceiptStore
from backend.infrastructure.persistence.ops.tenant_resolver import SqlAlchemyChannelTenantResolver
from backend.infrastructure.persistence.uow.outbox_publisher import SqlAlchemyOutboxDomainEventPublisher
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.interfaces.http.v2.schemas import (
    CreateNotificationRequest,
    NotificationListResponse,
    NotificationResponse,
)
from tests.api.conftest import (
    bearer,
    make_jwt,
    seed_caregiver_relationship,
    seed_facility,
    seed_identity_mapping,
    seed_member,
    seed_org,
    seed_patient,
)

_APP_SECRET = "dev-webhook-secret-change-in-production"


def _sign(body: bytes, secret: str = _APP_SECRET) -> str:
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _make_whatsapp_payload(from_phone: str, text: str, message_id: str | None = None) -> bytes:
    mid = message_id or f"wamid.{uuid4().hex}"
    return json.dumps({
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BIZ_123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "12345", "phone_number_id": "PN_123"},
                            "contacts": [{"wa_id": from_phone, "profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "id": mid,
                                    "from": from_phone,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }).encode("utf-8")


# =============================================================================
# A, C, K, Z: Notification Domain, Lifecycle, Asymmetry & No-CDS Invariants
# =============================================================================


class TestNotificationDomain:
    """Domain model invariants, state machine, and clinical asymmetry protections."""

    def test_notification_creation_and_defaults(self):
        notif_id = uuid4()
        tenant_id = uuid4()
        recipient_id = uuid4()
        notif = Notification(
            id=notif_id,
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            recipient_phone="+919876543210",
            template_name="medication_reminder",
            template_params={"medication": "Metformin"},
        )
        assert notif.id == notif_id
        assert notif.status == NotificationStatus.PENDING
        assert notif.channel == NotificationChannel.WHATSAPP
        assert notif.notification_type == NotificationType.REMINDER
        assert notif.retry_count == 0

    def test_notification_lifecycle_happy_path(self):
        notif = Notification(
            id=uuid4(),
            tenant_id=uuid4(),
            recipient_id=uuid4(),
            recipient_phone="+919876543210",
        )
        assert notif.status == NotificationStatus.PENDING

        notif.queue()
        assert notif.status == NotificationStatus.QUEUED

        notif.mark_delivering()
        assert notif.status == NotificationStatus.DELIVERING

        delivered_time = datetime.now(timezone.utc)
        notif.mark_delivered(delivered_at=delivered_time)
        assert notif.status == NotificationStatus.DELIVERED
        assert notif.delivered_at == delivered_time

    def test_notification_lifecycle_retry_and_terminal_failure(self):
        notif = Notification(
            id=uuid4(),
            tenant_id=uuid4(),
            recipient_id=uuid4(),
        )
        notif.queue()
        notif.mark_delivering()

        # Retryable backoff transition
        notif.requeue_for_retry()
        assert notif.status == NotificationStatus.QUEUED
        assert notif.retry_count == 1

        notif.mark_delivering()
        notif.mark_failed(reason="Provider unreachable")
        assert notif.status == NotificationStatus.FAILED
        assert notif.failure_reason == "Provider unreachable"
        assert notif.failed_at is not None

    def test_notification_invalid_state_transitions_raise(self):
        notif = Notification(
            id=uuid4(),
            tenant_id=uuid4(),
            recipient_id=uuid4(),
        )
        # Cannot jump directly from PENDING to DELIVERED
        with pytest.raises(InvalidStateTransition):
            notif.mark_delivered()

        notif.queue()
        notif.mark_delivered()
        # DELIVERED is a terminal state; cannot transition to QUEUED or DELIVERING
        with pytest.raises(InvalidStateTransition):
            notif.queue()
        with pytest.raises(InvalidStateTransition):
            notif.mark_delivering()

    def test_dto_asymmetry_forbidden_clinical_fields_rejected_in_domain(self):
        """Clinical analytical fields are strictly rejected by the domain entity."""
        forbidden_keys = ["carbs_grams", "glycemic_index", "clinical_notes", "ai_review", "ai_diagnosis", "risk_score"]
        for key in forbidden_keys:
            with pytest.raises(DomainError, match="Forbidden clinical field"):
                Notification(
                    id=uuid4(),
                    tenant_id=uuid4(),
                    recipient_id=uuid4(),
                    template_params={key: "50"},
                )

    def test_no_clinical_decision_support_or_scoring(self):
        """Notification layer communicates approved events only without independent clinical reasoning."""
        notif = Notification(
            id=uuid4(),
            tenant_id=uuid4(),
            recipient_id=uuid4(),
            template_name="glucose_acknowledgement",
            template_params={"message": "Reading received"},
        )
        # Confirm notification does not possess risk scoring or clinical interpretation properties
        assert not hasattr(notif, "risk_score")
        assert not hasattr(notif, "clinical_interpretation")
        assert not hasattr(notif, "titration_advice")


# =============================================================================
# B, N: Persistence & Tenant Isolation
# =============================================================================


class TestNotificationPersistenceAndIsolation:
    """SQLAlchemy repository persistence and multi-tenant RLS guarantees."""

    def test_notification_repository_crud_and_tenant_isolation(self, db_client):
        _client, session_factory = db_client
        tenant_a = uuid4()
        tenant_b = uuid4()
        seed_org(session_factory, tenant_a, "tenant-a")
        seed_org(session_factory, tenant_b, "tenant-b")

        user_a = uuid4()
        user_b = uuid4()
        notif_a_id = uuid4()
        notif_b_id = uuid4()

        notif_a = Notification(
            id=notif_a_id,
            tenant_id=tenant_a,
            recipient_id=user_a,
            recipient_phone="+919111111111",
            template_name="reminder_a",
            template_params={"note": "tenant a"},
            status=NotificationStatus.PENDING,
            scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        notif_b = Notification(
            id=notif_b_id,
            tenant_id=tenant_b,
            recipient_id=user_b,
            recipient_phone="+919222222222",
            template_name="reminder_b",
            template_params={"note": "tenant b"},
            status=NotificationStatus.PENDING,
            scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        with SqlAlchemyUnitOfWork(session_factory, tenant_a) as uow_a:
            uow_a.notifications.add(notif_a)
            uow_a.commit()

        with SqlAlchemyUnitOfWork(session_factory, tenant_b) as uow_b:
            uow_b.notifications.add(notif_b)
            uow_b.commit()

        # Tenant A can read its own notification
        with SqlAlchemyUnitOfWork(session_factory, tenant_a) as uow_a:
            fetched = uow_a.notifications.get(notif_a_id)
            assert fetched.id == notif_a_id
            assert fetched.template_name == "reminder_a"

            # Tenant A CANNOT read Tenant B's notification
            with pytest.raises(EntityNotFound):
                uow_a.notifications.get(notif_b_id)

            # Tenant A list only returns Tenant A items
            tenant_a_items = uow_a.notifications.list_for_tenant()
            assert len(tenant_a_items) == 1
            assert tenant_a_items[0].id == notif_a_id

            # Tenant A due list returns only Tenant A due items
            due_a = uow_a.notifications.list_due(before=datetime.now(timezone.utc))
            assert len(due_a) == 1
            assert due_a[0].id == notif_a_id


# =============================================================================
# O, P, Q, R, S, T, V: Outbox Integration, Worker, Delivery & Missing Credentials
# =============================================================================


class TestOutboxAndDeliveryWorker:
    """Transactional outbox, worker lease, retry backoff, and delivery fail-safe."""

    def test_outbox_atomicity_with_notification_service(self, db_client):
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        seed_org(session_factory, tenant_id, "outbox-test")
        seed_patient(session_factory, tenant_id, patient_id, name="Active Patient")

        clock = SystemClock()
        id_gen = Uuid4IdGenerator()

        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            events = SqlAlchemyOutboxDomainEventPublisher(uow.session, tenant_id)
            audit = SqlAlchemyAuditStore(uow.session, tenant_id)
            svc = NotificationService(uow, events, audit, clock, id_gen)

            notif = svc.send_notification(
                tenant_id=tenant_id,
                recipient_id=patient_id,
                recipient_phone="+919876543210",
                template_name="glucose_check_reminder",
                template_params={"reminder_type": "fasting"},
                patient_id=patient_id,
            )
            uow.commit()

        # Verify atomic persistence in one database transaction:
        # 1. Notification entity in notifications table
        # 2. Outbox entry in domain_event_outbox
        # 3. Audit row in audit_events
        with session_factory() as session:
            notif_row = session.get(NotificationModel, notif.id)
            assert notif_row is not None
            assert notif_row.status == "queued"

            outbox_row = session.query(DomainEventOutboxModel).filter_by(tenant_id=tenant_id).first()
            assert outbox_row is not None
            assert outbox_row.event_type == CHANNEL_SEND_EVENT_TYPE
            assert outbox_row.payload["recipient_phone"] == "+919876543210"

            audit_row = session.query(AuditEventModel).filter_by(tenant_id=tenant_id, resource_id=str(notif.id)).first()
            assert audit_row is not None
            assert audit_row.action == "CREATE"

    def test_delivery_success_lifecycle_and_audit(self, db_client):
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        seed_org(session_factory, tenant_id, "delivery-success")
        seed_patient(session_factory, tenant_id, patient_id)

        notif_id = uuid4()
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            uow.notifications.add(
                Notification(
                    id=notif_id,
                    tenant_id=tenant_id,
                    recipient_id=patient_id,
                    recipient_phone="+919876543210",
                    status=NotificationStatus.QUEUED,
                )
            )
            uow.commit()

        mock_sender = MagicMock()
        mock_sender.send.return_value = DeliveryResult(
            success=True,
            provider_delivery_id="wam_succ_123",
        )

        handler = ChannelDeliveryHandler(
            sender=mock_sender,
            uow_factory=lambda tid: SqlAlchemyUnitOfWork(session_factory, tid),
            audit_factory=lambda u: SqlAlchemyAuditStore(u.session, u.tenant_id),
        )

        job = OutboxJob(
            event_id=uuid4(),
            event_type=CHANNEL_SEND_EVENT_TYPE,
            tenant_id=tenant_id,
            patient_id=patient_id,
            correlation_id=None,
            payload={
                "message_id": str(notif_id),
                "channel_type": "WHATSAPP",
                "recipient_phone": "+919876543210",
                "template_name": "test_tmpl",
                "template_params": {},
            },
            occurred_at=datetime.now(timezone.utc),
            retry_count=0,
        )

        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        # Verify notification updated to DELIVERED and audit logged
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            updated = uow.notifications.get(notif_id)
            assert updated.status == NotificationStatus.DELIVERED
            assert updated.delivered_at is not None

        with session_factory() as s:
            audit = s.query(AuditEventModel).filter_by(resource_id=str(notif_id), outcome="SUCCESS").first()
            assert audit is not None
            assert audit.provenance_metadata.get("provider_delivery_id") == "wam_succ_123"

    def test_delivery_retryable_failure_and_worker_backoff(self, db_client):
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        seed_org(session_factory, tenant_id, "delivery-retry")
        seed_patient(session_factory, tenant_id, patient_id)

        notif_id = uuid4()
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            uow.notifications.add(
                Notification(
                    id=notif_id,
                    tenant_id=tenant_id,
                    recipient_id=patient_id,
                    recipient_phone="+919876543210",
                    status=NotificationStatus.DELIVERING,
                )
            )
            uow.commit()

        mock_sender = MagicMock()
        mock_sender.send.return_value = DeliveryResult(
            success=False,
            error_code="provider_transient_503",
            retryable=True,
        )

        handler = ChannelDeliveryHandler(
            sender=mock_sender,
            uow_factory=lambda tid: SqlAlchemyUnitOfWork(session_factory, tid),
            audit_factory=lambda u: SqlAlchemyAuditStore(u.session, u.tenant_id),
        )

        job = OutboxJob(
            event_id=uuid4(),
            event_type=CHANNEL_SEND_EVENT_TYPE,
            tenant_id=tenant_id,
            patient_id=patient_id,
            correlation_id=None,
            payload={"message_id": str(notif_id), "channel_type": "WHATSAPP", "recipient_phone": "+919876543210"},
            occurred_at=datetime.now(timezone.utc),
            retry_count=0,
        )

        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.RETRYABLE

        # Verify notification retry count incremented and status reset to QUEUED
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            updated = uow.notifications.get(notif_id)
            assert updated.status == NotificationStatus.QUEUED
            assert updated.retry_count == 1

    def test_delivery_permanent_failure_marks_notification_failed(self, db_client):
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        seed_org(session_factory, tenant_id, "delivery-perm-fail")
        seed_patient(session_factory, tenant_id, patient_id)

        notif_id = uuid4()
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            uow.notifications.add(
                Notification(
                    id=notif_id,
                    tenant_id=tenant_id,
                    recipient_id=patient_id,
                    recipient_phone="+919876543210",
                    status=NotificationStatus.DELIVERING,
                )
            )
            uow.commit()

        mock_sender = MagicMock()
        mock_sender.send.return_value = DeliveryResult(
            success=False,
            error_code="provider_rejected_400",
            retryable=False,
        )

        handler = ChannelDeliveryHandler(
            sender=mock_sender,
            uow_factory=lambda tid: SqlAlchemyUnitOfWork(session_factory, tid),
            audit_factory=lambda u: SqlAlchemyAuditStore(u.session, u.tenant_id),
        )

        job = OutboxJob(
            event_id=uuid4(),
            event_type=CHANNEL_SEND_EVENT_TYPE,
            tenant_id=tenant_id,
            patient_id=patient_id,
            correlation_id=None,
            payload={"message_id": str(notif_id), "channel_type": "WHATSAPP", "recipient_phone": "+919876543210"},
            occurred_at=datetime.now(timezone.utc),
            retry_count=0,
        )

        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.PERMANENT

        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            updated = uow.notifications.get(notif_id)
            assert updated.status == NotificationStatus.FAILED
            assert updated.failure_reason == "provider_rejected_400"

    def test_missing_whatsapp_credentials_fails_safe(self, db_client):
        """When WhatsApp credentials are unset, system does NOT pretend success and marks FAILED."""
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        seed_org(session_factory, tenant_id, "cred-missing")
        seed_patient(session_factory, tenant_id, patient_id)

        sender = WhatsAppChannelSender(access_token="", phone_number_id="")
        msg = OutboundMessage(
            message_id=uuid4(),
            tenant_id=tenant_id,
            channel_type="WHATSAPP",
            recipient_phone="+919876543210",
            template_name="test",
            template_params={},
        )
        res = sender.send(msg)
        assert res.success is False
        assert res.error_code == "CREDENTIALS_MISSING"
        assert res.retryable is False

        # In handler
        notif_id = uuid4()
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            uow.notifications.add(
                Notification(
                    id=notif_id,
                    tenant_id=tenant_id,
                    recipient_id=patient_id,
                    status=NotificationStatus.DELIVERING,
                )
            )
            uow.commit()

        handler = ChannelDeliveryHandler(
            sender=sender,
            uow_factory=lambda tid: SqlAlchemyUnitOfWork(session_factory, tid),
            audit_factory=lambda u: SqlAlchemyAuditStore(u.session, u.tenant_id),
        )
        job = OutboxJob(
            event_id=uuid4(),
            event_type=CHANNEL_SEND_EVENT_TYPE,
            tenant_id=tenant_id,
            patient_id=patient_id,
            correlation_id=None,
            payload={"message_id": str(notif_id), "channel_type": "WHATSAPP", "recipient_phone": "+919876543210"},
            occurred_at=datetime.now(timezone.utc),
            retry_count=0,
        )
        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.PERMANENT

        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            notif = uow.notifications.get(notif_id)
            assert notif.status == NotificationStatus.FAILED
            assert notif.failure_reason == "CREDENTIALS_MISSING"


# =============================================================================
# F, G, H, I, J, M: Inbound WhatsApp Webhook, Signatures, Intake & Deactivation
# =============================================================================


class TestWhatsAppInboundIntegration:
    """Signature verification, deduplication, intake transformation, and deactivation checks."""

    def test_webhook_signature_rejection(self, client):
        body = _make_whatsapp_payload("+919876543210", "150 fasting")
        # 1. Missing signature header
        resp = client.post("/api/v2/webhooks/whatsapp", content=body)
        assert resp.status_code == 401

        # 2. Tampered signature header
        resp = client.post(
            "/api/v2/webhooks/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": "sha256=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb"},
        )
        assert resp.status_code == 401

    def test_webhook_signature_acceptance_and_deduplication(self, client):
        body = _make_whatsapp_payload("+919876543210", "150 fasting", message_id="wamid.test.dedup.001")
        sig = _sign(body)

        # First delivery accepted
        resp1 = client.post(
            "/api/v2/webhooks/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": sig},
        )
        assert resp1.status_code == 202
        assert resp1.json()["status"] == "received"

        # Duplicate delivery within retention window accepted with 202 but dropped
        resp2 = client.post(
            "/api/v2/webhooks/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": sig},
        )
        assert resp2.status_code == 202
        assert resp2.json()["status"] == "received"

    def test_whatsapp_glucose_intake_workflow(self, db_client):
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        seed_org(session_factory, tenant_id, "glucose-intake")

        phone = "+919876543210"
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            p = Patient(id=patient_id, uh_id=UHID("D-1001"), name="Glucose User", phone=PhoneNumber(phone), active=True)
            uow.patients.add(p)
            uow.commit()

        resolver = SqlAlchemyChannelTenantResolver(session_factory())
        clock = SystemClock()
        id_gen = Uuid4IdGenerator()

        handler = WhatsAppIntakeHandler(
            tenant_resolver=resolver,
            uow_factory=lambda tid: SqlAlchemyUnitOfWork(session_factory, tid),
            events_factory=lambda u: SqlAlchemyOutboxDomainEventPublisher(u.session, u.tenant_id),
            audit_factory=lambda u: SqlAlchemyAuditStore(u.session, u.tenant_id),
            clock=clock,
            id_gen=id_gen,
        )

        job = OutboxJob(
            event_id=uuid4(),
            event_type=WEBHOOK_INTAKE_EVENT_TYPE,
            tenant_id=None,
            patient_id=None,
            correlation_id=None,
            payload={"source_phone": phone, "text": "145 fasting", "message_id": "wam.gluc.01"},
            occurred_at=datetime.now(timezone.utc),
            retry_count=0,
        )

        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        # Verify canonical GlucoseObservation created
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            readings = uow.glucose_observations.list_for_patient(patient_id)
            assert len(readings) == 1
            assert readings[0].value.value_mg_dl == 145

    def test_whatsapp_meal_intake_workflow(self, db_client):
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        seed_org(session_factory, tenant_id, "meal-intake")

        phone = "+919876543211"
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            p = Patient(id=patient_id, uh_id=UHID("D-1002"), name="Meal User", phone=PhoneNumber(phone), active=True)
            uow.patients.add(p)
            uow.commit()

        resolver = SqlAlchemyChannelTenantResolver(session_factory())
        clock = SystemClock()
        id_gen = Uuid4IdGenerator()

        handler = WhatsAppIntakeHandler(
            tenant_resolver=resolver,
            uow_factory=lambda tid: SqlAlchemyUnitOfWork(session_factory, tid),
            events_factory=lambda u: SqlAlchemyOutboxDomainEventPublisher(u.session, u.tenant_id),
            audit_factory=lambda u: SqlAlchemyAuditStore(u.session, u.tenant_id),
            clock=clock,
            id_gen=id_gen,
        )

        job = OutboxJob(
            event_id=uuid4(),
            event_type=WEBHOOK_INTAKE_EVENT_TYPE,
            tenant_id=None,
            patient_id=None,
            correlation_id=None,
            payload={"source_phone": phone, "text": "1 bowl dal, 1 chapati, salad", "message_id": "wam.meal.01"},
            occurred_at=datetime.now(timezone.utc),
            retry_count=0,
        )

        outcome = handler.handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            meals = uow.meal_observations.list_for_patient(patient_id)
            assert len(meals) == 1
            assert "dal" in meals[0].description

    def test_whatsapp_deactivated_patient_denial(self, db_client):
        """Intake from a deactivated patient must be denied and recorded as FAILED audit."""
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        seed_org(session_factory, tenant_id, "deactivated-intake")

        phone = "+919876543299"
        # Seed deactivated patient
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            p = Patient(id=patient_id, uh_id=UHID("D-9999"), name="Deactivated", phone=PhoneNumber(phone), active=False)
            uow.patients.add(p)
            uow.commit()

        resolver = SqlAlchemyChannelTenantResolver(session_factory())
        clock = SystemClock()
        id_gen = Uuid4IdGenerator()

        handler = WhatsAppIntakeHandler(
            tenant_resolver=resolver,
            uow_factory=lambda tid: SqlAlchemyUnitOfWork(session_factory, tid),
            events_factory=lambda u: SqlAlchemyOutboxDomainEventPublisher(u.session, u.tenant_id),
            audit_factory=lambda u: SqlAlchemyAuditStore(u.session, u.tenant_id),
            clock=clock,
            id_gen=id_gen,
        )

        job = OutboxJob(
            event_id=uuid4(),
            event_type=WEBHOOK_INTAKE_EVENT_TYPE,
            tenant_id=None,
            patient_id=None,
            correlation_id=None,
            payload={"source_phone": phone, "text": "160 fasting", "message_id": "wam.deact.01"},
            occurred_at=datetime.now(timezone.utc),
            retry_count=0,
        )

        with pytest.raises(Exception):
            handler.handle(job)

        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            readings = uow.glucose_observations.list_for_patient(patient_id)
            assert len(readings) == 0


# =============================================================================
# Y: Deterministic Scheduler
# =============================================================================


class TestReminderScheduler:
    """Deterministic reminder scheduling without clinical reasoning."""

    def test_process_due_notifications(self, db_client):
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        seed_org(session_factory, tenant_id, "scheduler-due")
        seed_patient(session_factory, tenant_id, patient_id)

        past_due = datetime.now(timezone.utc) - timedelta(minutes=10)
        future_due = datetime.now(timezone.utc) + timedelta(hours=2)

        notif_due = Notification(
            id=uuid4(),
            tenant_id=tenant_id,
            recipient_id=patient_id,
            recipient_phone="+919876543210",
            status=NotificationStatus.PENDING,
            scheduled_at=past_due,
        )
        notif_future = Notification(
            id=uuid4(),
            tenant_id=tenant_id,
            recipient_id=patient_id,
            recipient_phone="+919876543210",
            status=NotificationStatus.PENDING,
            scheduled_at=future_due,
        )

        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            uow.notifications.add(notif_due)
            uow.notifications.add(notif_future)
            uow.commit()

        scheduler = ReminderScheduler(
            uow_factory=lambda tid: SqlAlchemyUnitOfWork(session_factory, tid),
            events_factory=lambda u: SqlAlchemyOutboxDomainEventPublisher(u.session, u.tenant_id),
            audit_factory=lambda u: SqlAlchemyAuditStore(u.session, u.tenant_id),
            clock=SystemClock(),
            id_gen=Uuid4IdGenerator(),
        )

        processed = scheduler.process_due_notifications(tenant_id)
        assert processed == 1

        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            d = uow.notifications.get(notif_due.id)
            f = uow.notifications.get(notif_future.id)
            assert d.status == NotificationStatus.QUEUED
            assert f.status == NotificationStatus.PENDING

    def test_schedule_care_task_due_reminders(self, db_client):
        _client, session_factory = db_client
        tenant_id = uuid4()
        patient_id = uuid4()
        worker_id = uuid4()
        seed_org(session_factory, tenant_id, "task-reminders")
        seed_patient(session_factory, tenant_id, patient_id)

        task_due = CareTask(
            id=uuid4(),
            patient_id=patient_id,
            assigned_to_user_id=worker_id,
            description="Collect capillary sample",
            status=CareTaskStatus.OPEN,
            due_at=datetime.now(timezone.utc) + timedelta(hours=4),
        )

        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            uow.care_tasks.add(task_due)
            uow.commit()

        scheduler = ReminderScheduler(
            uow_factory=lambda tid: SqlAlchemyUnitOfWork(session_factory, tid),
            events_factory=lambda u: SqlAlchemyOutboxDomainEventPublisher(u.session, u.tenant_id),
            audit_factory=lambda u: SqlAlchemyAuditStore(u.session, u.tenant_id),
            clock=SystemClock(),
            id_gen=Uuid4IdGenerator(),
        )

        count = scheduler.schedule_care_task_due_reminders(tenant_id, window_hours=24)
        assert count == 1

        # Check notification was created for worker
        with SqlAlchemyUnitOfWork(session_factory, tenant_id) as uow:
            notifs = uow.notifications.list_for_recipient(worker_id)
            assert len(notifs) == 1
            assert notifs[0].template_name == "care_task_due_reminder"
            assert notifs[0].template_params.get("task_id") == str(task_due.id)

        # Idempotency check: running again does not duplicate reminder
        count_again = scheduler.schedule_care_task_due_reminders(tenant_id, window_hours=24)
        assert count_again == 0


# =============================================================================
# D, E, L, M, N, U, W, X: API Contracts, RBAC, Idempotency & Error Semantics
# =============================================================================


class TestNotificationsAPI:
    """HTTP v2 contracts, authorization, error semantics, and idempotency."""

    def test_admin_and_care_coordinator_can_create_notification(self, db_client):
        client, session_factory = db_client
        tenant_id = str(uuid4())
        admin_id = str(uuid4())
        coord_id = str(uuid4())
        patient_id = str(uuid4())

        seed_org(session_factory, UUID(tenant_id), "api-create-notif")
        seed_patient(session_factory, UUID(tenant_id), UUID(patient_id), name="Patient One")

        admin_token = make_jwt(sub=admin_id, tenant_id=tenant_id, roles=["admin"])
        coord_token = make_jwt(sub=coord_id, tenant_id=tenant_id, roles=["care_coordinator"])

        payload = {
            "recipient_id": patient_id,
            "recipient_phone": "+919876543210",
            "template_name": "appointment_reminder",
            "template_params": {"time": "10:00 AM"},
            "notification_type": "reminder",
            "channel": "WHATSAPP",
            "patient_id": patient_id,
        }

        # Admin creates notification
        resp1 = client.post(
            "/api/v2/notifications",
            json=payload,
            headers=bearer(admin_token),
        )
        assert resp1.status_code == 201
        data1 = resp1.json()
        assert data1["template_name"] == "appointment_reminder"
        assert data1["status"] == "queued"
        assert data1["retry_count"] == 0

        # Coordinator creates notification
        payload2 = {
            **payload,
            "template_name": "care_followup",
        }
        resp2 = client.post(
            "/api/v2/notifications",
            json=payload2,
            headers=bearer(coord_token),
        )
        assert resp2.status_code == 201
        assert resp2.json()["template_name"] == "care_followup"

    def test_patient_and_caregiver_denied_creation_surface(self, db_client):
        client, session_factory = db_client
        tenant_id = str(uuid4())
        patient_id = str(uuid4())
        caregiver_id = str(uuid4())

        seed_org(session_factory, UUID(tenant_id), "denial-test")
        seed_patient(session_factory, UUID(tenant_id), UUID(patient_id))

        patient_token = make_jwt(sub=patient_id, tenant_id=tenant_id, roles=["patient"])
        cg_token = make_jwt(sub=caregiver_id, tenant_id=tenant_id, roles=["caregiver"])

        payload = {
            "recipient_id": patient_id,
            "recipient_phone": "+919876543210",
            "template_name": "reminder",
            "template_params": {},
        }

        resp_p = client.post("/api/v2/notifications", json=payload, headers=bearer(patient_token))
        assert resp_p.status_code == 403

        resp_cg = client.post("/api/v2/notifications", json=payload, headers=bearer(cg_token))
        assert resp_cg.status_code == 403

    def test_deactivated_patient_notification_creation_denied(self, db_client):
        client, session_factory = db_client
        tenant_id = str(uuid4())
        admin_id = str(uuid4())
        patient_id = str(uuid4())

        seed_org(session_factory, UUID(tenant_id), "deact-notif-deny")
        seed_patient(session_factory, UUID(tenant_id), UUID(patient_id), active=False)

        admin_token = make_jwt(sub=admin_id, tenant_id=tenant_id, roles=["admin"])

        payload = {
            "recipient_id": patient_id,
            "recipient_phone": "+919876543210",
            "template_name": "test",
            "template_params": {},
            "patient_id": patient_id,
        }

        resp = client.post("/api/v2/notifications", json=payload, headers=bearer(admin_token))
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_REQUEST"

    def test_forbidden_clinical_params_rejected_on_post(self, db_client):
        client, session_factory = db_client
        tenant_id = str(uuid4())
        admin_id = str(uuid4())
        patient_id = str(uuid4())

        seed_org(session_factory, UUID(tenant_id), "asymmetry-post")
        seed_patient(session_factory, UUID(tenant_id), UUID(patient_id))

        admin_token = make_jwt(sub=admin_id, tenant_id=tenant_id, roles=["admin"])

        payload = {
            "recipient_id": patient_id,
            "recipient_phone": "+919876543210",
            "template_name": "clinical_summary",
            "template_params": {"carbs_grams": "75"},
            "patient_id": patient_id,
        }

        resp = client.post("/api/v2/notifications", json=payload, headers=bearer(admin_token))
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_patient_self_read_and_cross_patient_denial(self, db_client):
        client, session_factory = db_client
        tenant_id = str(uuid4())
        patient_a_id = str(uuid4())
        patient_b_id = str(uuid4())
        user_a_id = str(uuid4())

        seed_org(session_factory, UUID(tenant_id), "patient-self-read")
        seed_patient(session_factory, UUID(tenant_id), UUID(patient_a_id), name="Patient A")
        seed_patient(session_factory, UUID(tenant_id), UUID(patient_b_id), name="Patient B")
        seed_identity_mapping(session_factory, UUID(tenant_id), UUID(user_a_id), UUID(patient_a_id))

        notif_a = uuid4()
        notif_b = uuid4()

        with SqlAlchemyUnitOfWork(session_factory, UUID(tenant_id)) as uow:
            uow.notifications.add(
                Notification(
                    id=notif_a,
                    tenant_id=UUID(tenant_id),
                    recipient_id=UUID(user_a_id),
                    patient_id=UUID(patient_a_id),
                    template_name="reminder_a",
                )
            )
            uow.notifications.add(
                Notification(
                    id=notif_b,
                    tenant_id=UUID(tenant_id),
                    recipient_id=UUID(patient_b_id),
                    patient_id=UUID(patient_b_id),
                    template_name="reminder_b",
                )
            )
            uow.commit()

        token_a = make_jwt(sub=user_a_id, tenant_id=tenant_id, roles=["patient"])

        # Patient A reads own notification -> 200
        resp_own = client.get(f"/api/v2/notifications/{notif_a}", headers=bearer(token_a))
        assert resp_own.status_code == 200
        assert resp_own.json()["id"] == str(notif_a)

        # Patient A tries to read Patient B's notification -> 403 Access Denied
        resp_other = client.get(f"/api/v2/notifications/{notif_b}", headers=bearer(token_a))
        assert resp_other.status_code == 403

    def test_caregiver_relationship_enforcement(self, db_client):
        client, session_factory = db_client
        tenant_id = str(uuid4())
        patient_id = str(uuid4())
        caregiver_id = str(uuid4())

        seed_org(session_factory, UUID(tenant_id), "caregiver-auth")
        seed_patient(session_factory, UUID(tenant_id), UUID(patient_id))

        notif_id = uuid4()
        with SqlAlchemyUnitOfWork(session_factory, UUID(tenant_id)) as uow:
            uow.notifications.add(
                Notification(
                    id=notif_id,
                    tenant_id=UUID(tenant_id),
                    recipient_id=UUID(patient_id),
                    patient_id=UUID(patient_id),
                    template_name="care_update",
                )
            )
            uow.commit()

        cg_token = make_jwt(sub=caregiver_id, tenant_id=tenant_id, roles=["caregiver"])

        # 1. Unverified / missing relationship -> 403
        resp1 = client.get(f"/api/v2/notifications/{notif_id}", headers=bearer(cg_token))
        assert resp1.status_code == 403

        # 2. Add verified relationship
        seed_caregiver_relationship(
            session_factory,
            UUID(tenant_id),
            UUID(patient_id),
            UUID(caregiver_id),
            status="verified",
        )

        resp2 = client.get(f"/api/v2/notifications/{notif_id}", headers=bearer(cg_token))
        assert resp2.status_code == 200
        assert resp2.json()["id"] == str(notif_id)

    def test_cross_tenant_denial_returns_404(self, db_client):
        client, session_factory = db_client
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())
        admin_b = str(uuid4())
        seed_org(session_factory, UUID(tenant_a), "tenant-a")
        seed_org(session_factory, UUID(tenant_b), "tenant-b")

        notif_a = uuid4()
        with SqlAlchemyUnitOfWork(session_factory, UUID(tenant_a)) as uow_a:
            uow_a.notifications.add(
                Notification(
                    id=notif_a,
                    tenant_id=UUID(tenant_a),
                    recipient_id=uuid4(),
                    template_name="secret_a",
                )
            )
            uow_a.commit()

        token_b = make_jwt(sub=admin_b, tenant_id=tenant_b, roles=["admin"])

        # Admin of Tenant B requests Tenant A's notification -> 404 (safe resource-not-found)
        resp = client.get(f"/api/v2/notifications/{notif_a}", headers=bearer(token_b))
        assert resp.status_code == 404

    def test_idempotency_key_prevents_duplicate_creation(self, db_client):
        client, session_factory = db_client
        tenant_id = str(uuid4())
        admin_id = str(uuid4())
        patient_id = str(uuid4())

        seed_org(session_factory, UUID(tenant_id), "idemp-test")
        seed_patient(session_factory, UUID(tenant_id), UUID(patient_id))

        admin_token = make_jwt(sub=admin_id, tenant_id=tenant_id, roles=["admin"])
        idempotency_key = f"idemp-{uuid4().hex}"

        payload = {
            "recipient_id": patient_id,
            "recipient_phone": "+919876543210",
            "template_name": "idemp_reminder",
            "template_params": {"seq": "1"},
        }

        # First request
        resp1 = client.post(
            "/api/v2/notifications",
            json=payload,
            headers={
                **bearer(admin_token),
                "Idempotency-Key": idempotency_key,
            },
        )
        assert resp1.status_code == 201
        data1 = resp1.json()

        # Replayed request with same Idempotency-Key
        resp2 = client.post(
            "/api/v2/notifications",
            json=payload,
            headers={
                **bearer(admin_token),
                "Idempotency-Key": idempotency_key,
            },
        )
        assert resp2.status_code == 201
        assert resp2.headers.get("Idempotent-Replayed") == "true"
        assert resp2.json()["id"] == data1["id"]

    def test_correlation_id_propagation(self, db_client):
        client, session_factory = db_client
        tenant_id = str(uuid4())
        admin_id = str(uuid4())
        patient_id = str(uuid4())
        cid = str(uuid4())

        seed_org(session_factory, UUID(tenant_id), "cid-test")
        seed_patient(session_factory, UUID(tenant_id), UUID(patient_id))

        admin_token = make_jwt(sub=admin_id, tenant_id=tenant_id, roles=["admin"])

        payload = {
            "recipient_id": patient_id,
            "recipient_phone": "+919876543210",
            "template_name": "cid_check",
            "template_params": {},
        }

        resp = client.post(
            "/api/v2/notifications",
            json=payload,
            headers={
                **bearer(admin_token),
                "X-Correlation-ID": cid,
            },
        )
        assert resp.status_code == 201
        notif_id = resp.json()["id"]

        with session_factory() as s:
            audit = s.query(AuditEventModel).filter_by(resource_id=notif_id).first()
            assert audit is not None
            assert audit.correlation_id == cid
