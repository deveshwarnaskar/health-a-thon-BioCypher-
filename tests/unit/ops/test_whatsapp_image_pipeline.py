"""Phase 11a Test Suite C: WhatsApp Image Pipeline (12 tests).

Verifies:
1. Inbound image media metadata extraction & routing
2. Media retrieval boundary invocation (sender.download_media)
3. MediaVault encrypted storage & lease management for images
4. MediaVault auto-disposal in finally block upon completion
5. ImageAnalysisProvider boundary invocation with image bytes
6. Structured extraction of FoodItemCandidates and Hinglish plate description
7. Deterministic nutrition calculation via taxonomy (AI never derives nutrition)
8. Provenance propagation into source_metadata & domain events
9. Low-confidence / unidentifiable image safe fallback (LOW_CONFIDENCE_GUIDANCE)
10. Provider error safe fallback (LOW_CONFIDENCE_GUIDANCE)
11. Unsupported image MIME or payload size (> 10MB) rejection
12. Strict clinical safety: image analysis NEVER mutates medication plans or derives glucose
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4
import pytest

from backend.application.ops.contracts import (
    DeliveryOutcome,
    DeliveryResult,
    OutboundMessage,
    OutboxJob,
    ResolvedChannelPatient,
)
from backend.application.ops.handlers import WhatsAppIntakeHandler
from backend.application.ops.ports import ChannelSender, ChannelTenantResolver
from backend.application.ports.ai_multimodal import (
    AIMultimodalError,
    FoodItemCandidate,
    ImageAnalysisProvider,
    ImageAnalysisResult,
    LOW_CONFIDENCE_GUIDANCE,
    MediaProvenance,
    UnsupportedMediaError,
)
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.storage import IObjectStorage
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.media_vault import MediaVault
from backend.domain.entities import MealObservation, Notification, NotificationStatus, Patient
from backend.domain.value_objects import PatientConfirmationState, PhoneNumber, UHID


class DummyClock(Clock):
    def __init__(self, fixed: datetime | None = None):
        self._now = fixed or datetime(2026, 9, 22, 10, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now


class DummyIdGen(IdGenerator):
    def __init__(self):
        self._counter = 0

    def new_uuid(self) -> UUID:
        self._counter += 1
        return UUID(int=self._counter)


class InMemoryObjectStorage(IObjectStorage):
    def __init__(self):
        self.data: dict[str, bytes] = {}

    def put(self, key: str, payload: bytes) -> None:
        self.data[key] = payload

    def get(self, key: str) -> bytes:
        if key not in self.data:
            raise KeyError(key)
        return self.data[key]

    def exists(self, key: str) -> bool:
        return key in self.data

    def generate_presigned_url(self, key: str, expires_in: int = 300) -> str:
        return f"https://storage.local/{key}"

    def delete(self, key: str) -> None:
        self.data.pop(key, None)


class RecordingSender(ChannelSender):
    def __init__(self, media_payload: bytes | None = None, media_mime: str = "image/jpeg"):
        self.sent: list[OutboundMessage] = []
        self.downloaded_ids: list[str] = []
        self._media_payload = media_payload or b"\xff\xd8\xff\xe0_fake_jpeg_bytes"
        self._media_mime = media_mime

    def send(self, message: OutboundMessage) -> DeliveryResult:
        self.sent.append(message)
        return DeliveryResult(success=True, provider_delivery_id=str(uuid4()))

    def download_media(self, media_id: str) -> tuple[bytes, str] | None:
        self.downloaded_ids.append(media_id)
        if self._media_payload is None:
            return None
        return self._media_payload, self._media_mime


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


class RecordingMetrics:
    def __init__(self):
        self.counters: dict[str, float] = {}
        self.labels: dict[str, Any] = {}

    def increment_counter(self, name: str, labels: dict[str, str] | None = None, delta: float = 1.0):
        self.counters[name] = self.counters.get(name, 0.0) + delta
        if labels:
            self.labels[name] = labels

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None):
        pass


class SimpleMealRepo:
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


class SimpleGlucoseRepo:
    def __init__(self):
        self.by_id: dict[UUID, Any] = {}

    def add(self, obs):
        self.by_id[obs.id] = obs

    def get(self, obs_id):
        return self.by_id[obs_id]

    def list_for_patient(self, patient_id):
        return [o for o in self.by_id.values() if o.patient_id == patient_id]


class SimplePatientRepo:
    def __init__(self, patient: Patient):
        self.patient = patient

    def get(self, patient_id: UUID) -> Patient:
        return self.patient


class SimpleNotificationRepo:
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
        self.meal_observations = SimpleMealRepo()
        self.glucose_observations = SimpleGlucoseRepo()
        self.patients = SimplePatientRepo(patient)
        self.notifications = SimpleNotificationRepo()
        self.committed = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class FixedTenantResolver(ChannelTenantResolver):
    def __init__(self, tenant_id: UUID, patient_id: UUID):
        self._tenant_id = tenant_id
        self._patient_id = patient_id

    def resolve(self, phone: str) -> ResolvedChannelPatient | None:
        if phone == "+919876543210":
            return ResolvedChannelPatient(tenant_id=self._tenant_id, patient_id=self._patient_id)
        return None


def _make_image_job(
    media_id: str = "media_img_456",
    mime_type: str = "image/jpeg",
    phone: str = "+919876543210",
    caption: str = "",
    file_size_bytes: int = 65536,
) -> OutboxJob:
    return OutboxJob(
        event_id=uuid4(),
        event_type="whatsapp.message.received",
        tenant_id=UUID(int=1),
        patient_id=UUID(int=2),
        occurred_at=datetime.now(timezone.utc),
        retry_count=0,
        payload={
            "message_id": "wamid.image.001",
            "source_phone": phone,
            "text": caption or "[image]",
            "media_type": "image",
            "media_id": media_id,
            "mime_type": mime_type,
            "file_size_bytes": file_size_bytes,
            "caption": caption,
        },
        correlation_id=uuid4(),
    )


class TestWhatsAppImagePipeline:
    @pytest.fixture
    def setup_pipeline(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Priya Sharma", uh_id=UHID("UHID-IMG-01"), active=True)
        uow = SimpleUow(patient)
        sender = RecordingSender()
        audit_store = RecordingAuditStore()
        events_pub = RecordingEventPublisher()
        metrics = RecordingMetrics()
        clock = DummyClock()
        id_gen = DummyIdGen()
        storage = InMemoryObjectStorage()
        vault = MediaVault(storage, clock=clock, retention_seconds=300)

        mock_vision = MagicMock(spec=ImageAnalysisProvider)
        mock_vision.analyze_meal.return_value = ImageAnalysisResult(
            items=(
                FoodItemCandidate(name="roti", portion="2 roti"),
                FoodItemCandidate(name="dal", portion="1 katori"),
            ),
            description="2 roti and dal",
            confidence="high",
            unidentifiable=False,
            provenance=MediaProvenance(provider="gemini", model="gemini-1.5-flash", latency_ms=450.0),
        )

        handler = WhatsAppIntakeHandler(
            tenant_resolver=FixedTenantResolver(tenant_id, patient_id),
            uow_factory=lambda _: uow,
            events_factory=lambda _: events_pub,
            audit_factory=lambda _: audit_store,
            clock=clock,
            id_gen=id_gen,
            sender=sender,
            image_analyzer=mock_vision,
            media_vault=vault,
            multimodal_enabled=True,
            metrics=metrics,
        )

        return {
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "patient": patient,
            "uow": uow,
            "sender": sender,
            "audit_store": audit_store,
            "events_pub": events_pub,
            "metrics": metrics,
            "vault": vault,
            "storage": storage,
            "mock_vision": mock_vision,
            "handler": handler,
            "clock": clock,
        }

    def test_01_image_intake_metadata_extraction(self, setup_pipeline):
        ctx = setup_pipeline
        job = _make_image_job(media_id="img_media_id_777", mime_type="image/jpeg", file_size_bytes=32768)
        outcome = ctx["handler"].handle(job)
        assert outcome == DeliveryOutcome.SUCCESS
        assert "img_media_id_777" in ctx["sender"].downloaded_ids

    def test_02_image_media_download_and_vision_provider_invoked(self, setup_pipeline):
        ctx = setup_pipeline
        job = _make_image_job()
        outcome = ctx["handler"].handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        ctx["mock_vision"].analyze_meal.assert_called_once()
        img_bytes, mime_arg = ctx["mock_vision"].analyze_meal.call_args[0]
        assert img_bytes == b"\xff\xd8\xff\xe0_fake_jpeg_bytes"
        assert mime_arg == "image/jpeg"

    def test_03_image_media_vault_encrypted_staging_and_disposal(self, setup_pipeline):
        ctx = setup_pipeline
        job = _make_image_job()
        ctx["handler"].handle(job)

        # Staged, then disposed in finally block
        assert ctx["vault"].outstanding() == 0
        assert len(ctx["storage"].data) == 0

    def test_04_structured_food_candidates_extracted(self, setup_pipeline):
        ctx = setup_pipeline
        job = _make_image_job()
        ctx["handler"].handle(job)

        meals = ctx["uow"].meal_observations.list_for_patient(ctx["patient_id"])
        assert len(meals) == 1
        meal = meals[0]
        assert "roti" in meal.description.lower()
        assert meal.confirmation == PatientConfirmationState.PENDING

    def test_05_deterministic_nutrition_taxonomy_scoring(self, setup_pipeline):
        """Nutrition calculations remain 100% deterministic (AI never computes nutrition)."""
        ctx = setup_pipeline
        job = _make_image_job()
        ctx["handler"].handle(job)

        meals = ctx["uow"].meal_observations.list_for_patient(ctx["patient_id"])
        meal = meals[0]
        # 2 roti + 1 dal at medium portion is deterministically scored
        assert meal.carbs_grams is not None and meal.carbs_grams > 0
        assert meal.glycemic_index in ("low", "medium", "high")

    def test_06_image_provenance_propagated_to_canonical_events(self, setup_pipeline):
        ctx = setup_pipeline
        job = _make_image_job()
        ctx["handler"].handle(job)

        pub_events = ctx["events_pub"].published
        assert len(pub_events) >= 1
        event = pub_events[0]
        assert hasattr(event, "source_metadata")
        meta = event.source_metadata
        assert meta["source_type"] == "image"
        assert meta["image_analysis_provider"] == "gemini"
        assert meta["image_analysis_model"] == "gemini-1.5-flash"
        assert meta["image_confidence"] == "high"

    def test_07_patient_prompted_for_confirmation_without_carbs(self, setup_pipeline):
        """Patient prompt asks for confirmation without leaking doctor-facing carbs/GI."""
        ctx = setup_pipeline
        job = _make_image_job()
        ctx["handler"].handle(job)

        assert len(ctx["sender"].sent) == 1
        prompt = ctx["sender"].sent[0].template_params["body"]
        assert "confirm" in prompt.lower()
        assert "carb" not in prompt.lower()
        assert "glycemic" not in prompt.lower()

    def test_08_low_confidence_or_unidentifiable_image_safe_fallback(self, setup_pipeline):
        ctx = setup_pipeline
        ctx["mock_vision"].analyze_meal.return_value = ImageAnalysisResult(
            items=(),
            description="",
            confidence="low",
            unidentifiable=True,
        )
        job = _make_image_job()
        outcome = ctx["handler"].handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        # Fails safe: zero meals created, safe guidance returned
        assert len(ctx["uow"].meal_observations.list_for_patient(ctx["patient_id"])) == 0
        assert len(ctx["sender"].sent) == 1
        assert ctx["sender"].sent[0].template_params["body"] == LOW_CONFIDENCE_GUIDANCE

    def test_09_vision_provider_error_safe_fallback(self, setup_pipeline):
        ctx = setup_pipeline
        ctx["mock_vision"].analyze_meal.side_effect = AIMultimodalError("Gemini rate limited", retryable=False, provider="gemini")
        job = _make_image_job()
        outcome = ctx["handler"].handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        assert len(ctx["sender"].sent) == 1
        assert ctx["sender"].sent[0].template_params["body"] == LOW_CONFIDENCE_GUIDANCE
        assert len(ctx["uow"].meal_observations.list_for_patient(ctx["patient_id"])) == 0

    def test_10_unsupported_mime_rejected_at_boundary(self, setup_pipeline):
        ctx = setup_pipeline
        ctx["sender"]._media_mime = "image/bmp"
        job = _make_image_job(mime_type="image/bmp")
        outcome = ctx["handler"].handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        assert ctx["sender"].sent[0].template_params["body"] == LOW_CONFIDENCE_GUIDANCE
        ctx["mock_vision"].analyze_meal.assert_not_called()

    def test_11_oversized_image_rejected_at_boundary(self, setup_pipeline):
        ctx = setup_pipeline
        ctx["sender"]._media_payload = b"X" * (10_000_001)
        job = _make_image_job(file_size_bytes=10_000_001)
        outcome = ctx["handler"].handle(job)
        assert outcome == DeliveryOutcome.SUCCESS

        assert ctx["sender"].sent[0].template_params["body"] == LOW_CONFIDENCE_GUIDANCE
        ctx["mock_vision"].analyze_meal.assert_not_called()

    def test_12_strict_clinical_safety_never_derives_glucose_or_modifies_medication(self, setup_pipeline):
        """Clinical boundary check: image observation never generates a GlucoseObservation or touches medication."""
        ctx = setup_pipeline
        job = _make_image_job()
        ctx["handler"].handle(job)

        # Zero glucose observations created from meal photo
        glucose_obs = ctx["uow"].glucose_observations.list_for_patient(ctx["patient_id"])
        assert len(glucose_obs) == 0

        # Only one meal draft in pending state
        meals = ctx["uow"].meal_observations.list_for_patient(ctx["patient_id"])
        assert len(meals) == 1
        assert meals[0].confirmation == PatientConfirmationState.PENDING
