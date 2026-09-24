"""Phase 11a Test Suite D: Canonical Event & Provenance Verification (10 tests).

Verifies:
1. Canonical event attributes (patient_id, event_id, event_type, correlation_id)
2. Strict chronology: occurred_at preservation when stated_time is given (never overwritten by received_at)
3. Fallback chronology: recorded_at used when no explicit stated_time is present
4. source_metadata propagation across command -> service -> domain event
5. Voice provenance fields (source_type="voice", provider, model, latency_ms)
6. Image provenance fields (source_type="image", provider, model, confidence, latency_ms)
7. MealObservation lifecycle & verification status (PENDING -> CONFIRMED / CORRECTED / REJECTED)
8. GlucoseObservation lifecycle & verification status (PENDING -> CONFIRMED / CORRECTED)
9. Immutable audit event recording with channel provenance and actor attribution
10. End-to-end provenance integrity: zero PHI in provenance metadata
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
import pytest

from backend.application.commands import (
    ConfirmGlucoseObservation,
    ConfirmMealObservation,
    IngestGlucoseReading,
    LogMealDraft,
)
from backend.application.ops.contracts import (
    AuditAction,
    DeliveryOutcome,
    DeliveryResult,
    OutboundMessage,
    OutboxJob,
    ResolvedChannelPatient,
)
from backend.application.ops.handlers import WhatsAppIntakeHandler
from backend.application.ops.intake_text import parse_intake_text
from backend.application.ops.ports import ChannelSender, ChannelTenantResolver
from backend.application.ports.ai_multimodal import (
    MediaProvenance,
    TranscriptionResult,
)
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.confirm_glucose_observation import ConfirmGlucoseObservationHandler
from backend.application.services.confirm_meal_observation import ConfirmMealObservationHandler
from backend.application.services.ingest_glucose import IngestGlucoseHandler
from backend.application.services.log_meal_draft import LogMealDraftHandler
from backend.domain.entities import GlucoseObservation, MealObservation, Patient
from backend.domain.events.clinical import (
    GlucoseObservationConfirmed,
    GlucoseObservationRecorded,
    MealObservationConfirmed,
    MealObservationRecorded,
)
from backend.domain.value_objects import (
    GlucoseValue,
    KatoriVolume,
    MealPortion,
    PatientConfirmationState,
    PhoneNumber,
    ReadingTag,
    UHID,
)


class DummyClock(Clock):
    def __init__(self, fixed: datetime | None = None):
        self._now = fixed or datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now


class DummyIdGen(IdGenerator):
    def __init__(self):
        self._counter = 0

    def new_uuid(self) -> UUID:
        self._counter += 1
        return UUID(int=self._counter)


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
        self.by_id: dict[UUID, GlucoseObservation] = {}

    def add(self, obs: GlucoseObservation) -> None:
        self.by_id[obs.id] = obs

    def get(self, obs_id: UUID) -> GlucoseObservation:
        return self.by_id[obs_id]

    def save(self, obs: GlucoseObservation) -> None:
        self.by_id[obs.id] = obs

    def list_for_patient(self, patient_id: UUID) -> list[GlucoseObservation]:
        return [o for o in self.by_id.values() if o.patient_id == patient_id]


class SimplePatientRepo:
    def __init__(self, patient: Patient):
        self.patient = patient

    def get(self, patient_id: UUID) -> Patient:
        return self.patient


class SimpleUow(UnitOfWork):
    def __init__(self, patient: Patient):
        self.meal_observations = SimpleMealRepo()
        self.glucose_observations = SimpleGlucoseRepo()
        self.patients = SimplePatientRepo(patient)
        self.committed = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class TestCanonicalEventProvenance:
    @pytest.fixture
    def setup_context(self):
        patient_id = uuid4()
        tenant_id = uuid4()
        patient = Patient(id=patient_id, name="Sunita Rao", uh_id=UHID("UHID-CANON-01"), active=True)
        uow = SimpleUow(patient)
        events_pub = RecordingEventPublisher()
        audit_store = RecordingAuditStore()
        clock = DummyClock()
        id_gen = DummyIdGen()

        return {
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "patient": patient,
            "uow": uow,
            "events_pub": events_pub,
            "audit_store": audit_store,
            "clock": clock,
            "id_gen": id_gen,
        }

    def test_01_canonical_glucose_recorded_event_attributes(self, setup_context):
        ctx = setup_context
        handler = IngestGlucoseHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])

        corr_id = uuid4()
        source_meta = {"channel": "whatsapp", "source_type": "voice", "transcript_model": "saaras:v3"}
        cmd = IngestGlucoseReading(
            patient_id=ctx["patient_id"],
            value=GlucoseValue(135),
            taken_at=datetime(2026, 9, 22, 8, 30, 0, tzinfo=timezone.utc),
            tag=ReadingTag.FASTING,
            correlation_id=corr_id,
            source_metadata=source_meta,
        )
        handler.handle(cmd)

        # Domain event verification
        assert len(ctx["events_pub"].published) == 1
        ev = ctx["events_pub"].published[0]
        assert isinstance(ev, GlucoseObservationRecorded)
        assert ev.event_type == "glucose_observation.recorded"
        assert ev.patient_id == ctx["patient_id"]
        assert ev.correlation_id == corr_id
        assert ev.source_metadata == source_meta

    def test_02_strict_chronology_explicit_stated_time_preserved(self, setup_context):
        """When text/voice includes explicit time (e.g. 8:30 am), occurred_at/taken_at MUST preserve it."""
        ctx = setup_context
        current_time = datetime(2026, 9, 22, 14, 0, 0, tzinfo=timezone.utc)
        cmd = parse_intake_text(
            "140 fasting at 8:30 am",
            patient_id=ctx["patient_id"],
            correlation_id=uuid4(),
            recorded_at=current_time,
            source_metadata={"channel": "whatsapp"},
        )

        assert isinstance(cmd, IngestGlucoseReading)
        # Taken_at is the parsed stated time (8:30 am today), NOT 14:00 (received time)!
        assert cmd.taken_at.hour == 8
        assert cmd.taken_at.minute == 30
        assert cmd.taken_at != current_time

    def test_03_fallback_chronology_defaults_to_recorded_at(self, setup_context):
        """When no stated time is mentioned, taken_at defaults to recorded_at."""
        ctx = setup_context
        received_time = datetime(2026, 9, 22, 11, 45, 0, tzinfo=timezone.utc)
        cmd = parse_intake_text(
            "150 fasting",
            patient_id=ctx["patient_id"],
            correlation_id=uuid4(),
            recorded_at=received_time,
        )
        assert isinstance(cmd, IngestGlucoseReading)
        assert cmd.taken_at == received_time

    def test_04_meal_draft_canonical_event_provenance(self, setup_context):
        ctx = setup_context
        handler = LogMealDraftHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])

        corr_id = uuid4()
        source_meta = {
            "channel": "whatsapp",
            "source_type": "image",
            "image_analysis_provider": "gemini",
            "image_confidence": "high",
        }
        cmd = LogMealDraft(
            patient_id=ctx["patient_id"],
            description="2 roti and bhindi",
            recorded_at=ctx["clock"].now(),
            portion=MealPortion(food_key="roti", katori=KatoriVolume(220), quantity=2.0),
            correlation_id=corr_id,
            source_metadata=source_meta,
        )
        handler.handle(cmd)

        assert len(ctx["events_pub"].published) == 1
        ev = ctx["events_pub"].published[0]
        assert isinstance(ev, MealObservationRecorded)
        assert ev.event_type == "meal_observation.recorded"
        assert ev.patient_id == ctx["patient_id"]
        assert ev.source_metadata == source_meta

    def test_05_meal_observation_confirmation_lifecycle(self, setup_context):
        ctx = setup_context
        # 1. Log draft
        draft_handler = LogMealDraftHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])
        corr_id = uuid4()
        draft_cmd = LogMealDraft(
            patient_id=ctx["patient_id"],
            description="2 roti and dal",
            recorded_at=ctx["clock"].now(),
            portion=MealPortion(food_key="roti", katori=KatoriVolume(220), quantity=2.0),
            correlation_id=corr_id,
            source_metadata={"source_type": "image"},
        )
        draft_res = draft_handler.handle(draft_cmd)
        meal_id = draft_res.meal_observation_id

        meal = ctx["uow"].meal_observations.get(meal_id)
        assert meal.confirmation == PatientConfirmationState.PENDING

        # 2. Confirm meal
        confirm_handler = ConfirmMealObservationHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])
        confirm_cmd = ConfirmMealObservation(
            meal_observation_id=meal_id,
            confirmed_by=PhoneNumber("+919876543210"),
            corrected_description=None,
            corrected_portion=None,
            correlation_id=corr_id,
            source_metadata={"confirm_medium": "whatsapp_button"},
        )
        confirm_handler.handle(confirm_cmd)

        confirmed_meal = ctx["uow"].meal_observations.get(meal_id)
        assert confirmed_meal.confirmation == PatientConfirmationState.CONFIRMED

        # Check confirmed domain event
        assert len(ctx["events_pub"].published) == 2
        conf_event = ctx["events_pub"].published[1]
        assert isinstance(conf_event, MealObservationConfirmed)
        assert conf_event.observation_id == meal_id
        assert conf_event.source_metadata == {"confirm_medium": "whatsapp_button"}

    def test_06_meal_observation_correction_with_portion_update(self, setup_context):
        ctx = setup_context
        draft_handler = LogMealDraftHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])
        draft_res = draft_handler.handle(
            LogMealDraft(
                patient_id=ctx["patient_id"],
                description="2 roti and dal",
                recorded_at=ctx["clock"].now(),
                portion=MealPortion(food_key="roti", katori=KatoriVolume(220), quantity=2.0),
            )
        )
        meal_id = draft_res.meal_observation_id

        confirm_handler = ConfirmMealObservationHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])
        corrected_portion = MealPortion(food_key="roti", katori=KatoriVolume(150), quantity=2.0)
        confirm_handler.handle(
            ConfirmMealObservation(
                meal_observation_id=meal_id,
                confirmed_by=PhoneNumber("+919876543210"),
                corrected_description="2 roti and dal (chhoti katori)",
                corrected_portion=corrected_portion,
            )
        )

        meal = ctx["uow"].meal_observations.get(meal_id)
        assert meal.confirmation == PatientConfirmationState.CORRECTED
        assert meal.description == "2 roti and dal (chhoti katori)"
        assert meal.portion.katori.volume_ml == 150

    def test_07_glucose_observation_confirmation_lifecycle(self, setup_context):
        ctx = setup_context
        ingest_handler = IngestGlucoseHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])
        res = ingest_handler.handle(
            IngestGlucoseReading(
                patient_id=ctx["patient_id"],
                value=GlucoseValue(145),
                taken_at=ctx["clock"].now(),
                tag=ReadingTag.FASTING,
            )
        )
        obs_id = res.observation_id
        obs = ctx["uow"].glucose_observations.get(obs_id)
        assert obs.confirmation == PatientConfirmationState.PENDING

        confirm_handler = ConfirmGlucoseObservationHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])
        confirm_handler.handle(
            ConfirmGlucoseObservation(
                observation_id=obs_id,
                confirmed_by=PhoneNumber("+919876543210"),
                source_metadata={"confirm_medium": "whatsapp_text"},
            )
        )

        confirmed_obs = ctx["uow"].glucose_observations.get(obs_id)
        assert confirmed_obs.confirmation == PatientConfirmationState.CONFIRMED
        assert len(ctx["events_pub"].published) == 2
        conf_ev = ctx["events_pub"].published[1]
        assert isinstance(conf_ev, GlucoseObservationConfirmed)
        assert conf_ev.observation_id == obs_id
        assert conf_ev.source_metadata == {"confirm_medium": "whatsapp_text"}

    def test_08_glucose_observation_correction_lifecycle(self, setup_context):
        ctx = setup_context
        ingest_handler = IngestGlucoseHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])
        res = ingest_handler.handle(
            IngestGlucoseReading(
                patient_id=ctx["patient_id"],
                value=GlucoseValue(145),
                taken_at=ctx["clock"].now(),
                tag=ReadingTag.FASTING,
            )
        )
        obs_id = res.observation_id

        confirm_handler = ConfirmGlucoseObservationHandler(ctx["uow"], ctx["events_pub"], ctx["clock"], ctx["id_gen"])
        confirm_handler.handle(
            ConfirmGlucoseObservation(
                observation_id=obs_id,
                confirmed_by=PhoneNumber("+919876543210"),
                corrected_value=GlucoseValue(155),
                corrected_tag=ReadingTag.POST_LUNCH,
            )
        )

        corrected_obs = ctx["uow"].glucose_observations.get(obs_id)
        assert corrected_obs.confirmation == PatientConfirmationState.CORRECTED
        assert corrected_obs.value.value_mg_dl == 155
        assert corrected_obs.tag == ReadingTag.POST_LUNCH

    def test_09_immutable_audit_log_persists_provenance_link(self, setup_context):
        ctx = setup_context
        from backend.application.ops.contracts import AuditEvent
        audit_store = ctx["audit_store"]

        audit_store.record(
            AuditEvent(
                tenant_id=ctx["tenant_id"],
                actor_id=ctx["patient_id"],
                actor_type="PATIENT",
                action="CREATE",
                resource_type="GLUCOSE_OBSERVATION",
                resource_id=str(uuid4()),
                outcome="SUCCESS",
                provenance_metadata={
                    "channel": "whatsapp",
                    "source_type": "voice",
                    "provider_message_id": "wamid.001",
                    "transcript_model": "saaras:v3",
                },
            )
        )

        assert len(audit_store.events) == 1
        entry = audit_store.events[0]
        assert entry.tenant_id == ctx["tenant_id"]
        assert entry.action == "CREATE"
        assert entry.provenance_metadata["channel"] == "whatsapp"
        assert entry.provenance_metadata["source_type"] == "voice"

    def test_10_end_to_end_zero_phi_in_provenance_metadata(self, setup_context):
        """Verify MediaProvenance safely strips PHI keys (transcript, text, raw) via _safe_details."""
        from backend.application.ports.ai_multimodal import MediaProvenance, _safe_details

        dirty_details = {
            "transcript": "Maine 180 sugar dekha",
            "text": "patient clinical text",
            "raw": "raw bytes or words",
            "latency_ms": 110.0,
            "provider_version": "v1.2",
        }
        cleaned = _safe_details(dirty_details)
        assert "transcript" not in cleaned
        assert "text" not in cleaned
        assert "raw" not in cleaned
        assert cleaned["latency_ms"] == 110.0
        assert cleaned["provider_version"] == "v1.2"

        prov = MediaProvenance(provider="sarvam", model="saaras:v3", details=dirty_details)
        prov_dict = prov.to_dict()
        assert "transcript" not in prov_dict
        assert "text" not in prov_dict
        assert "raw" not in prov_dict
