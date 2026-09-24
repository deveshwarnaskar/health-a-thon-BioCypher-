"""Gate 09 — transactional outbox worker CLI.

Runs the asynchronous pipeline without spawning anything: the worker leases
due outbox rows, dispatches them through the application-layer handlers, and
acknowledges / reschedules / dead-letters each event.

Modes:
    python -m backend.interfaces.cli.worker --once        # one batch, then exit
    python -m backend.interfaces.cli.worker --poll         # poll forever

Configuration comes from the standard settings (``THALI_DATABASE__URL``,
``THALI_WHATSAPP__*``). No process is auto-spawned by the API.
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlalchemy.orm import Session, sessionmaker

from backend.application.ops.contracts import (
    AI_GENERATION_EVENT_TYPE,
    CHANNEL_SEND_EVENT_TYPE,
    WEBHOOK_INTAKE_EVENT_TYPE,
)
from backend.application.ops.handlers import (
    AIGenerationJobHandler,
    ChannelDeliveryHandler,
    WhatsAppIntakeHandler,
)
from backend.application.services.evidence_builder import EvidenceBuilder
from backend.infrastructure.ai import DeterministicDemoProvider
from backend.application.ops.worker import OutboxWorker
from backend.infrastructure.channel.whatsapp_sender import WhatsAppChannelSender
from backend.infrastructure.config.clock import SystemClock
from backend.infrastructure.config.database import create_db_engine, create_session_factory
from backend.infrastructure.config.id_generator import Uuid4IdGenerator
from backend.infrastructure.persistence.ops.audit_store import SqlAlchemyAuditStore
from backend.infrastructure.persistence.ops.outbox_store import SqlAlchemyOutboxWorkerStore
from backend.infrastructure.persistence.ops.tenant_resolver import SqlAlchemyChannelTenantResolver
from backend.infrastructure.persistence.uow.outbox_publisher import (
    SqlAlchemyOutboxDomainEventPublisher,
)
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork

logger = logging.getLogger("gate09.worker.runner")


def _sarvam_configured(settings) -> bool:
    return bool(settings.ai.sarvam_api_key or settings.ai.provider == "sarvam")


def _build_multimodal_bundle(settings):
    """Assemble the provider-neutral multimodal bundle behind the settings switch.

    Every component is optional: when ``sarvam_enabled`` is false (the default)
    the bundle is inert and the ingestion pipeline runs the legacy path exactly
    as before. Providers are constructed lazily-safe — a missing credential never
    raises at startup; it fails safe (canonical guidance reply) at ingestion time.
    """
    from backend.application.ports.ai_multimodal import MultimodalProviderBundle

    enabled = bool(settings.ai.sarvam_enabled)
    speech_to_text = None
    language_identifier = None
    translation = None
    text_to_speech = None
    image_analysis = None

    if enabled:
        from backend.infrastructure.ai import (
            GeminiImageAnalysisProvider,
            SarvamClient,
            SarvamLanguageIdentifier,
            SarvamSpeechToTextProvider,
            SarvamTextToSpeechProvider,
            SarvamTranslationProvider,
        )

        client = SarvamClient() if _sarvam_configured(settings) else None
        if client is not None and client.is_configured:
            speech_to_text = SarvamSpeechToTextProvider(client)
            language_identifier = SarvamLanguageIdentifier(client)
            translation = SarvamTranslationProvider(client)
            text_to_speech = SarvamTextToSpeechProvider(client)
        if settings.ai.image_analysis_provider.lower() == "gemini":
            image_analysis = GeminiImageAnalysisProvider(
                api_key=settings.ai.api_key,
                model_name=settings.ai.model or "gemini-flash-lite-latest",
            )

    return MultimodalProviderBundle(
        speech_to_text=speech_to_text,
        language_identifier=language_identifier,
        translation=translation,
        text_to_speech=text_to_speech,
        image_analysis=image_analysis,
        enabled=enabled,
    )


def _build_media_vault(settings):
    """Encrypting transient-media store on top of the standard object storage."""
    from backend.application.services.media_vault import MediaVault
    from backend.infrastructure.storage.s3_storage import S3ObjectStorage

    return MediaVault(
        S3ObjectStorage(),
        retention_seconds=settings.ai.media_retention_seconds,
        encryption_key=settings.ai.media_encryption_key,
    )


class InfrastructureMetrics:
    """Bridges the application metrics port to the Prometheus registry."""

    def __init__(self) -> None:
        from backend.infrastructure.observability.metrics import get_metrics_registry

        self._registry = get_metrics_registry()

    def increment_counter(self, name, labels=None, delta=1.0):
        self._registry.counter(name).inc(delta, **(labels or {}))

    def observe_histogram(self, name, value, labels=None):
        self._registry.histogram(name).observe(value, **(labels or {}))


def build_worker(*, db_url: str | None, whatsapp_access_token: str | None = None,
                 whatsapp_phone_number_id: str | None = None) -> tuple[OutboxWorker, object]:
    """Wiring assembly: infrastructure factories → application handlers."""
    from config.settings import Settings

    settings = Settings()
    effective_url = db_url or settings.database.url or "sqlite:///:memory:"
    engine = create_db_engine(
        effective_url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
        pool_pre_ping=settings.database.pool_pre_ping,
        pool_reset_on_return="rollback",
    )
    session_factory: sessionmaker[Session] = create_session_factory(engine)

    clock = SystemClock()
    id_gen = Uuid4IdGenerator()

    def uow_factory(tenant_id):
        return SqlAlchemyUnitOfWork(session_factory, tenant_id)

    def events_factory(uow):
        return SqlAlchemyOutboxDomainEventPublisher(uow.session, uow.tenant_id)

    def audit_factory(uow):
        return SqlAlchemyAuditStore(uow.session, uow.tenant_id)

    store = SqlAlchemyOutboxWorkerStore(session_factory)
    handlers = {}

    sender = WhatsAppChannelSender(
        access_token=whatsapp_access_token or settings.whatsapp.access_token,
        phone_number_id=whatsapp_phone_number_id or settings.whatsapp.phone_number_id,
        api_version=settings.whatsapp.api_version,
    )

    sarvam_transcriber = None
    sarvam_completer = None
    multimodal = _build_multimodal_bundle(settings)
    media_vault = _build_media_vault(settings)
    if settings.ai.sarvam_api_key or settings.ai.provider == "sarvam":
        from backend.infrastructure.ai.sarvam_client import SarvamClient
        _sarvam = SarvamClient()
        if _sarvam.is_configured:
            def sarvam_transcriber(audio_bytes: bytes, mime_type: str) -> str | None:
                try:
                    res = _sarvam.transcribe_audio(audio_bytes, mime_type=mime_type)
                    return res.get("transcript")
                except Exception as exc:
                    logger.warning("sarvam audio transcription failed: %s", exc)
                    return None

            def sarvam_completer(user_msg: str, patient_name: str) -> str | None:
                try:
                    system_prompt = (
                        "You are the empathetic, culturally attuned Indic AI health companion for THALI x P.L.A.T.E. "
                        "Speak in warm, conversational Hinglish (Hindi written in Roman script) with respectful address (Ji). "
                        "Guidelines:\n"
                        "- Follow ICMR and RSSDI Indian dietary guidelines (Half plate vegetables/salad, 1/4 protein like dal/paneer/eggs, 1/4 whole grains like roti/brown rice).\n"
                        "- Do NOT prescribe, change, or recommend medication/insulin dosages.\n"
                        "- Keep answers concise (2-3 short paragraphs), practical, and encouraging."
                    )
                    res = _sarvam.chat_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"Patient: {patient_name}\nQuestion: {user_msg}"},
                        ],
                        temperature=0.2,
                        max_tokens=400,
                    )
                    return res.get("content", "").strip()
                except Exception as exc:
                    logger.warning("sarvam conversational completion failed: %s", exc)
                    return None

    intake = WhatsAppIntakeHandler(
        tenant_resolver=SqlAlchemyChannelTenantResolver(session_factory),
        uow_factory=uow_factory,
        events_factory=events_factory,
        audit_factory=audit_factory,
        clock=clock,
        id_gen=id_gen,
        sender=sender,
        transcriber=sarvam_transcriber,
        ai_completer=sarvam_completer,
        speech_to_text=multimodal.speech_to_text,
        language_identifier=multimodal.language_identifier,
        translator=multimodal.translation,
        image_analyzer=multimodal.image_analysis,
        media_vault=media_vault,
        multimodal_enabled=multimodal.enabled,
        metrics=InfrastructureMetrics(),
    )
    from backend.application.ops.conversation.engine import ConversationEngine
    from backend.application.ops.conversation.providers import (
        DeterministicConversationProvider,
        SarvamConversationProvider,
    )

    from backend.infrastructure.persistence.ops.conversation_session_store import (
        SqlAlchemyConversationSessionStore,
    )

    conv_ai = DeterministicConversationProvider()
    if _sarvam_configured(settings):
        from backend.infrastructure.ai.sarvam_client import SarvamClient

        try:
            conv_ai = SarvamConversationProvider(SarvamClient())
        except Exception:  # noqa: BLE001
            logger.warning("sarvam conversational provider unavailable; using deterministic")

    conversation_engine = ConversationEngine(
        clock=clock,
        id_gen=id_gen,
        ai_provider=conv_ai,
        session_store=SqlAlchemyConversationSessionStore(session_factory),
    )
    intake._conversation_engine = conversation_engine
    handlers[WEBHOOK_INTAKE_EVENT_TYPE] = intake.handle

    delivery = ChannelDeliveryHandler(
        sender=sender,
        uow_factory=uow_factory,
        audit_factory=audit_factory,
    )
    handlers[CHANNEL_SEND_EVENT_TYPE] = delivery.handle
    if not (sender._access_token and sender._phone_number_id):
        logger.warning("whatsapp credentials unset — outbound messages will fail-safe with explicit operational error")

    if settings.ai.provider == "sarvam" or settings.ai.sarvam_api_key:
        from backend.infrastructure.ai.sarvam_provider import SarvamAIProvider
        ai_provider = SarvamAIProvider(
            api_key=settings.ai.sarvam_api_key or settings.ai.api_key,
            model_name=settings.ai.sarvam_model or "sarvam-m",
            base_url=settings.ai.sarvam_base_url,
        )
    elif settings.ai.provider == "gemini" and settings.ai.api_key:
        from backend.infrastructure.ai.production_model_provider import ProductionModelProvider
        ai_provider = ProductionModelProvider(
            api_key=settings.ai.api_key,
            model_name=settings.ai.model or "gemini-1.5-flash",
        )
    else:
        ai_provider = DeterministicDemoProvider()

    evidence_builder = EvidenceBuilder()
    ai_handler = AIGenerationJobHandler(
        provider=ai_provider,
        evidence_builder=evidence_builder,
        uow_factory=uow_factory,
        audit_factory=audit_factory,
    )
    handlers[AI_GENERATION_EVENT_TYPE] = ai_handler.handle
    from backend.infrastructure.observability.worker_telemetry import WorkerTelemetryAdapter

    telemetry = WorkerTelemetryAdapter()
    from backend.application.ops.scheduler import ReminderScheduler

    scheduler = ReminderScheduler(
        uow_factory=uow_factory,
        events_factory=events_factory,
        audit_factory=audit_factory,
        clock=clock,
        id_gen=id_gen,
    )
    worker = OutboxWorker(store, handlers, worker_id=f"worker-{id(store)}", telemetry=telemetry)
    worker.scheduler = scheduler
    worker.session_factory = session_factory
    worker.media_vault = media_vault
    worker.media_sweep_interval = 60.0
    return worker, engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate 09 transactional outbox worker")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="process one batch and exit")
    mode.add_argument("--poll", action="store_true", help="poll for due events forever")
    parser.add_argument("--interval", type=float, default=0.5, help="poll idle sleep (seconds)")
    parser.add_argument("--db-url", default=None, help="override database URL")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    worker, _engine = build_worker(
        db_url=args.db_url,
    )
    logger.info("outbox worker ready (mode=%s)", "once" if args.once else "poll")

    if args.once:
        processed = worker.process_once()
        logger.info("processed %s job(s) in one batch", processed)
        return

    last_scheduler_check = 0.0
    scheduler_interval = 30.0  # evaluate chronobiological check-ins every 30 seconds
    last_media_sweep = 0.0

    while True:
        try:
            # Periodic encrypted-media retention sweep (multimodal layer)
            now_ts = time.time()
            if hasattr(worker, "media_vault") and worker.media_vault is not None:
                sweep_interval = getattr(worker, "media_sweep_interval", 60.0)
                if now_ts - last_media_sweep >= sweep_interval:
                    last_media_sweep = now_ts
                    try:
                        worker.media_vault.sweep()
                    except Exception:  # noqa: BLE001 - sweep must never kill the loop
                        logger.exception("media retention sweep failed; continuing")

            # Periodic chronobiological caregiver companion checks
            now_ts = time.time()
            if hasattr(worker, "scheduler") and hasattr(worker, "session_factory") and (now_ts - last_scheduler_check >= scheduler_interval):
                last_scheduler_check = now_ts
                try:
                    with worker.session_factory() as session:
                        from backend.infrastructure.persistence.models.tenant_models import OrganizationModel
                        active_tenants = [
                            r[0] for r in session.query(OrganizationModel.id).filter(OrganizationModel.active.is_(True)).all()
                        ]
                    for tid in active_tenants:
                        nudged = worker.scheduler.schedule_caregiver_companion_nudges(tid)
                        if nudged > 0:
                            logger.info("caregiver companion scheduled %s nudge(s) for tenant %s", nudged, tid)
                        worker.scheduler.process_due_notifications(tid)
                except Exception:
                    logger.exception("periodic caregiver companion check failed; continuing")

            processed = worker.process_once()
            if processed:
                logger.info("processed %s job(s)", processed)
                continue
        except Exception:  # noqa: BLE001 - a poll loop survives one bad batch
            logger.exception("worker batch failed; continuing")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()