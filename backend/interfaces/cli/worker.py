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


def build_worker(*, db_url: str | None, whatsapp_access_token: str | None = None,
                 whatsapp_phone_number_id: str | None = None) -> tuple[OutboxWorker, object]:
    """Wiring assembly: infrastructure factories → application handlers."""
    engine = create_db_engine(db_url)
    session_factory: sessionmaker[Session] = create_session_factory(engine)
    system_session = session_factory()

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

    intake = WhatsAppIntakeHandler(
        tenant_resolver=SqlAlchemyChannelTenantResolver(system_session),
        uow_factory=uow_factory,
        events_factory=events_factory,
        audit_factory=audit_factory,
        clock=clock,
        id_gen=id_gen,
    )
    handlers[WEBHOOK_INTAKE_EVENT_TYPE] = intake.handle

    sender = WhatsAppChannelSender(
        access_token=whatsapp_access_token,
        phone_number_id=whatsapp_phone_number_id,
    )
    delivery = ChannelDeliveryHandler(
        sender=sender,
        uow_factory=uow_factory,
        audit_factory=audit_factory,
    )
    handlers[CHANNEL_SEND_EVENT_TYPE] = delivery.handle
    if not (whatsapp_access_token and whatsapp_phone_number_id):
        logger.warning("whatsapp credentials unset — outbound messages will fail-safe with explicit operational error")

    ai_provider = DeterministicDemoProvider()
    evidence_builder = EvidenceBuilder()
    ai_handler = AIGenerationJobHandler(
        provider=ai_provider,
        evidence_builder=evidence_builder,
        uow_factory=uow_factory,
        audit_factory=audit_factory,
    )
    handlers[AI_GENERATION_EVENT_TYPE] = ai_handler.handle

    return OutboxWorker(store, handlers, worker_id=f"worker-{id(store)}"), engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate 09 transactional outbox worker")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="process one batch and exit")
    mode.add_argument("--poll", action="store_true", help="poll for due events forever")
    parser.add_argument("--interval", type=float, default=5.0, help="poll idle sleep (seconds)")
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

    while True:
        try:
            processed = worker.process_once()
            if processed:
                logger.info("processed %s job(s)", processed)
        except Exception:  # noqa: BLE001 - a poll loop survives one bad batch
            logger.exception("worker batch failed; continuing")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()