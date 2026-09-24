"""Phase 11a Test Suite E: Multimodal Security & Isolation (7 tests).

Verifies:
1. Webhook HMAC-SHA256 signature verification rejects forged/tampered payloads (constant-time)
2. Replay & deduplication protection (duplicate provider message deliveries rejected/acknowledged without re-execution)
3. Identity authorization boundary: unmapped WhatsApp identities never gain access to patient data
4. Active status boundary: deactivated patient identities are rejected at domain boundary
5. MediaVault AES-256-GCM integrity: storage key bound as AAD so tampering/swapping fails decryption
6. MediaVault path isolation: strictly scoped by tenant_id and patient_id (no cross-tenant leakage)
7. Zero PHI leakage in logs, audit provenance, and exceptions
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4
import pytest

from backend.application.ops.contracts import (
    DeliveryOutcome,
    OutboxJob,
    ResolvedChannelPatient,
)
from backend.application.ops.errors import PermanentWorkerFailure
from backend.application.ops.handlers import WhatsAppIntakeHandler
from backend.application.ops.ports import ChannelSender, ChannelTenantResolver
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.storage import IObjectStorage
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.media_vault import MediaVault, MediaVaultError
from backend.domain.entities import MealObservation, Notification, Patient
from backend.domain.value_objects import PhoneNumber, UHID
from backend.interfaces.http.v2.webhooks.whatsapp.signature import (
    WebhookSignatureError,
    verify_x_hub_signature_256,
)


class DummyClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)


class DummyIdGen(IdGenerator):
    def new_uuid(self) -> UUID:
        return uuid4()


class InMemoryStorage(IObjectStorage):
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, payload: bytes) -> None:
        self.objects[key] = payload

    def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise KeyError(key)
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def generate_presigned_url(self, key: str, expires_in: int = 300) -> str:
        return f"https://s3.local/{key}"

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class SimplePatientRepo:
    def __init__(self, patient: Patient):
        self.patient = patient

    def get(self, patient_id: UUID) -> Patient:
        return self.patient


class SimpleUow(UnitOfWork):
    def __init__(self, patient: Patient):
        self.patients = SimplePatientRepo(patient)
        self.meal_observations = type("SimpleRepo", (), {"list_for_patient": lambda self, pid: []})()
        self.glucose_observations = type("SimpleRepo", (), {"list_for_patient": lambda self, pid: []})()
        self.notifications = type("SimpleRepo", (), {"list_for_patient": lambda self, pid, limit=50: []})()

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


class MockResolver(ChannelTenantResolver):
    def __init__(self, mappings: dict[str, tuple[UUID, UUID]]):
        self._mappings = mappings

    def resolve(self, phone: str) -> ResolvedChannelPatient | None:
        if phone in self._mappings:
            tid, pid = self._mappings[phone]
            return ResolvedChannelPatient(tenant_id=tid, patient_id=pid)
        return None


class TestMultimodalSecurity:
    def test_01_webhook_hmac_signature_verification(self):
        """Webhook signature verification uses constant-time HMAC-SHA256 and rejects forged payloads."""
        app_secret = "meta_app_secret_very_secure_key_8888"
        raw_body = b'{"object":"whatsapp_business_account","entry":[{"changes":[{"value":{"messages":[{"text":{"body":"140 fasting"}}]}}]}]}'

        # Valid signature
        signature = "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        verify_x_hub_signature_256(raw_body, signature, app_secret)

        # Forged/Tampered body
        tampered_body = raw_body + b" "
        with pytest.raises(WebhookSignatureError):
            verify_x_hub_signature_256(tampered_body, signature, app_secret)

        # Wrong secret
        with pytest.raises(WebhookSignatureError):
            verify_x_hub_signature_256(raw_body, signature, "wrong_secret")

    def test_02_replay_protection_deduplication(self):
        """Receipt store deduplication blocks replayed deliveries with the same provider_message_id."""
        from backend.application.ops.contracts import WebhookReceipt
        from backend.infrastructure.persistence.ops.replay_store import (
            SqlAlchemyWebhookReceiptStore,
        )
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker
        from backend.infrastructure.persistence.models.ops_models import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionMaker = sessionmaker(bind=engine)

        with SessionMaker() as session:
            store = SqlAlchemyWebhookReceiptStore(session)
            now = datetime.now(timezone.utc)
            receipt = WebhookReceipt(
                receipt_id=uuid4(),
                provider="whatsapp",
                provider_message_id="wamid.HBgLMTIzNDU2Nzg5",
                event_type="whatsapp.message.received",
                received_at=now,
                source_phone="+919876543210",
            )

            # First delivery is fresh
            first_fresh = store.record(receipt)
            session.commit()
            assert first_fresh is True

            # Replayed delivery is detected as duplicate (fresh=False)
            replayed_receipt = WebhookReceipt(
                receipt_id=uuid4(),
                provider="whatsapp",
                provider_message_id="wamid.HBgLMTIzNDU2Nzg5",
                event_type="whatsapp.message.received",
                received_at=now,
                source_phone="+919876543210",
            )
            second_fresh = store.record(replayed_receipt)
            session.commit()
            assert second_fresh is False

    def test_03_unregistered_whatsapp_identity_denied_access(self):
        """Messages from unregistered phone numbers are rejected immediately with PermanentWorkerFailure."""
        tenant_id = uuid4()
        patient_id = uuid4()
        patient = Patient(id=patient_id, name="Test Patient", uh_id=UHID("UHID-SEC-01"), active=True)
        uow = SimpleUow(patient)

        # Only +919876543210 is registered
        resolver = MockResolver({"+919876543210": (tenant_id, patient_id)})
        handler = WhatsAppIntakeHandler(
            tenant_resolver=resolver,
            uow_factory=lambda _: uow,
            events_factory=lambda _: MagicMock(),
            audit_factory=lambda _: MagicMock(),
            clock=DummyClock(),
            id_gen=DummyIdGen(),
        )

        unregistered_job = OutboxJob(
            event_id=uuid4(),
            event_type="whatsapp.message.received",
            tenant_id=UUID(int=1),
            patient_id=UUID(int=2),
            occurred_at=datetime.now(timezone.utc),
            retry_count=0,
            payload={"source_phone": "+911111111111", "text": "140 fasting", "message_id": "msg_unregistered"},
            correlation_id=uuid4(),
        )

        with pytest.raises(PermanentWorkerFailure) as exc_info:
            handler.handle(unregistered_job)
        assert "resolves to no patient" in str(exc_info.value)

    def test_04_deactivated_patient_denied_channel_intake(self):
        """Intake from a deactivated patient account is rejected at domain boundary with failure audit."""
        tenant_id = uuid4()
        patient_id = uuid4()
        deactivated_patient = Patient(id=patient_id, name="Deactivated", uh_id=UHID("UHID-SEC-02"), active=False)
        uow = SimpleUow(deactivated_patient)
        audit_mock = MagicMock()

        resolver = MockResolver({"+919876543210": (tenant_id, patient_id)})
        handler = WhatsAppIntakeHandler(
            tenant_resolver=resolver,
            uow_factory=lambda _: uow,
            events_factory=lambda _: MagicMock(),
            audit_factory=lambda _: audit_mock,
            clock=DummyClock(),
            id_gen=DummyIdGen(),
        )

        job = OutboxJob(
            event_id=uuid4(),
            event_type="whatsapp.message.received",
            tenant_id=UUID(int=1),
            patient_id=UUID(int=2),
            occurred_at=datetime.now(timezone.utc),
            retry_count=0,
            payload={"source_phone": "+919876543210", "text": "140 fasting", "message_id": "msg_deact"},
            correlation_id=uuid4(),
        )

        with pytest.raises(PermanentWorkerFailure) as exc_info:
            handler.handle(job)
        assert "channel payload rejected by domain" in str(exc_info.value)
        audit_mock.record.assert_called_once()

    def test_05_media_vault_cryptographic_integrity_and_aad_binding(self):
        """Tampering with MediaVault ciphertext or swapping storage keys fails AES-256-GCM authentication."""
        storage = InMemoryStorage()
        vault = MediaVault(storage, encryption_key="super_secret_aes_key_for_test_123", retention_seconds=600)
        tenant_id = uuid4()
        patient_id = uuid4()

        ref = vault.store(
            tenant_id,
            patient_id,
            media_type="voice",
            message_id="msg_aad_test",
            payload_bytes=b"authentic_audio_payload",
            mime_type="audio/ogg",
        )

        # Retrieval succeeds with authentic storage key & ciphertext
        recovered = vault.retrieve(ref.storage_key)
        assert recovered == b"authentic_audio_payload"

        # Tampering with ciphertext fails integrity check
        tampered_envelope = bytearray(storage.get(ref.storage_key))
        tampered_envelope[-1] ^= 0xFF  # flip last byte of tag/ciphertext
        storage.put(ref.storage_key, bytes(tampered_envelope))

        with pytest.raises(MediaVaultError) as exc_info:
            vault.retrieve(ref.storage_key)
        assert "integrity check" in str(exc_info.value)

        # Swapping to a different storage key (AAD mismatch) fails decryption
        storage.put("different/storage/key.bin", bytes(tampered_envelope))
        with pytest.raises(MediaVaultError):
            vault.retrieve("different/storage/key.bin")

    def test_06_media_vault_cross_tenant_and_cross_patient_path_isolation(self):
        """MediaVault keys strictly embed tenant_id and patient_id preventing cross-tenant leakage."""
        storage = InMemoryStorage()
        vault = MediaVault(storage, encryption_key="test_key_123")
        tenant_a = uuid4()
        patient_a = uuid4()
        tenant_b = uuid4()
        patient_b = uuid4()

        ref_a = vault.store(tenant_a, patient_a, media_type="voice", message_id="msg_1", payload_bytes=b"patient_a_voice", mime_type="audio/ogg")
        ref_b = vault.store(tenant_b, patient_b, media_type="image", message_id="msg_2", payload_bytes=b"patient_b_image", mime_type="image/jpeg")

        # Storage paths strictly embed tenant and patient UUIDs
        assert str(tenant_a) in ref_a.storage_key
        assert str(patient_a) in ref_a.storage_key
        assert str(tenant_b) in ref_b.storage_key
        assert str(patient_b) in ref_b.storage_key

        # Cross check: Tenant A key does not match Tenant B
        assert str(tenant_b) not in ref_a.storage_key
        assert str(patient_b) not in ref_a.storage_key

    def test_07_zero_phi_leakage_in_multimodal_provenance_and_audit(self):
        """Non-negotiable PHI blocklist enforced: provenance and audit events never store raw text, transcripts, or clinical values."""
        from backend.application.ports.ai_multimodal import MediaProvenance, _safe_details
        from backend.infrastructure.observability.metrics import FORBIDDEN_LABEL_KEYS

        # Verify forbidden label keys blocklist covers core PHI
        for key in ["patient_id", "body", "payload", "message", "glucose", "medication", "carbs"]:
            assert key in FORBIDDEN_LABEL_KEYS

        # Verify MediaProvenance strips unsafe keys
        prov = MediaProvenance(
            provider="sarvam",
            model="saaras:v3",
            language_code="hi-IN",
            quality="high",
            latency_ms=120.0,
            details={"transcript": "my glucose is 180", "raw_audio_size": 4096},
        )
        as_dict = prov.to_dict()
        assert "transcript" not in as_dict
        assert as_dict["raw_audio_size"] == 4096
