"""Gate 09 — operational resiliency stores against real PostgreSQL.

Requires local PostgreSQL (autocreated throwaway database; skipped otherwise).

Verifies (all DB-engine-level, mirroring migration 0003):

1. Idempotency reservation concurrency: first-wins reservation, in-progress
   conflict, verbatim replay, fingerprint mismatch, expired-key recycle.
2. Webhook receipt deduplication (unique provider‖message_id).
3. Transactional outbox claim/mark lease behavior with backoff deadlines.
4. ``audit_events`` append-only immutability trigger.
5. ``resolve_channel_tenant`` SECURITY DEFINER routing function.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from backend.application.ops.contracts import DeliveryOutcome
from backend.domain.entities import Patient
from backend.domain.events.channel import WhatsAppMessageReceived
from backend.domain.value_objects import PhoneNumber, UHID
from backend.infrastructure.config.database import create_db_engine
from backend.infrastructure.persistence.models import (
    AuditEventModel,
    OrganizationModel,
    PatientModel,
)
from backend.infrastructure.persistence.ops.idempotency_store import SqlAlchemyIdempotencyStore
from backend.infrastructure.persistence.ops.outbox_store import SqlAlchemyOutboxWorkerStore
from backend.infrastructure.persistence.ops.replay_store import SqlAlchemyWebhookReceiptStore
from backend.infrastructure.persistence.ops.tenant_resolver import SqlAlchemyChannelTenantResolver
from backend.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
from backend.infrastructure.persistence.uow.outbox_publisher import SqlAlchemyOutboxDomainEventPublisher


@pytest.fixture(scope="module")
def postgres_ops_db():
    import psycopg

    db_name = f"thali_ops_{uuid4().hex[:8]}"
    try:
        with psycopg.connect("dbname=postgres", autocommit=True, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE {db_name};")
    except Exception:
        pytest.skip("Local PostgreSQL not accessible for integration testing")

    pg_url = f"postgresql+psycopg://@localhost:5432/{db_name}"
    engine = create_db_engine(pg_url)

    with engine.connect() as conn:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.attributes["connection"] = conn
        command.upgrade(alembic_cfg, "head")
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thali_app_test_role') THEN
                    CREATE ROLE thali_app_test_role WITH NOSUPERUSER NOBYPASSRLS;
                END IF;
            END
            $$;
            GRANT USAGE ON SCHEMA public TO thali_app_test_role;
            GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO thali_app_test_role;
            GRANT SELECT ON audit_events TO thali_app_test_role;
            GRANT EXECUTE ON FUNCTION public.resolve_channel_tenant(text) TO thali_app_test_role;
        """))
        conn.commit()

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    yield engine, session_factory

    engine.dispose()
    with psycopg.connect("dbname=postgres", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);")


def _seed_tenant(session_factory, slug: str):
    tenant = uuid4()
    with session_factory() as s:
        s.add(OrganizationModel(id=tenant, name=f"Ops {slug}", slug=slug))
        s.commit()
    return tenant


def test_idempotency_lifecycle_and_concurrency(postgres_ops_db):
    _, session_factory = postgres_ops_db
    tenant = _seed_tenant(session_factory, "idmp-live")
    actor = uuid4()
    key, fp = "req-1", "fingerprint-a"

    with session_factory() as s:
        first = SqlAlchemyIdempotencyStore(s).reserve(tenant, actor, key, fp)
        assert first.accepted
        s.commit()

    # A concurrent request on a separate connection observes in-progress.
    with session_factory() as s:
        concurrent = SqlAlchemyIdempotencyStore(s).reserve(tenant, actor, key, fp)
        assert not concurrent.accepted
        assert concurrent.conflict == "in_progress"

    # Winner completes; a retry replays the cached outcome verbatim.
    with session_factory() as s:
        store = SqlAlchemyIdempotencyStore(s)
        store.complete(tenant, actor, key, 201, {"Content-Type": "application/json"}, '{"id": 7}')
        s.commit()

    with session_factory() as s:
        replay = SqlAlchemyIdempotencyStore(s).reserve(tenant, actor, key, fp)
        assert replay.replay
        assert replay.status_code == 201
        assert replay.body == '{"id": 7}'

    # Same key with a different payload conflicts.
    with session_factory() as s:
        mismatch = SqlAlchemyIdempotencyStore(s).reserve(tenant, actor, key, "different-fingerprint")
        assert not mismatch.accepted
        assert mismatch.conflict == "mismatch"

    # Expired reservations are recycled and reusable under a new fingerprint.
    key2, fp2 = "req-2", "fingerprint-b"
    with session_factory() as s:
        SqlAlchemyIdempotencyStore(s).reserve(tenant, actor, key2, fp2, ttl_seconds=0)
        s.commit()
    with session_factory() as s:
        recycled = SqlAlchemyIdempotencyStore(s).reserve(tenant, actor, key2, fp2, ttl_seconds=3600)
        assert recycled.accepted


def test_webhook_receipt_dedup_on_postgres(postgres_ops_db):
    _, session_factory = postgres_ops_db
    pkey = f"wamid-pg-{uuid4()}"

    def _record():
        with session_factory() as s:
            store = SqlAlchemyWebhookReceiptStore(s)
            fresh = store.record(
                WebhookReceiptLike(pkey=pkey)
            )
            s.commit()
            return fresh

    assert _record() is True
    assert _record() is False


class WebhookReceiptLike:
    def __init__(self, pkey):
        self.receipt_id = uuid4()
        self.provider = "whatsapp"
        self.provider_message_id = pkey
        self.event_type = "message_received"
        self.received_at = datetime.now(timezone.utc)
        self.source_phone = "+919000000007"


def test_outbox_claim_mark_lease(postgres_ops_db):
    _, session_factory = postgres_ops_db
    tenant = _seed_tenant(session_factory, "outbox-live")

    with session_factory() as s:
        SqlAlchemyOutboxDomainEventPublisher(s, tenant).publish(
            whatsapp_event("msg-live-1")
        )
        s.commit()

    with session_factory() as s:
        jobs = SqlAlchemyOutboxWorkerStore(s).claim(10, "worker-live", 300)
        assert len(jobs) == 1
        assert jobs[0].event_type == "whatsapp.message.received"

        # Mark published → no longer eligible.
        SqlAlchemyOutboxWorkerStore(s).mark(jobs[0].event_id, DeliveryOutcome.SUCCESS)
        s.commit()
        assert SqlAlchemyOutboxWorkerStore(s).claim(10, "worker-live", 300) == []

    # A transient failure defers the row until its backoff deadline passes.
    with session_factory() as s:
        SqlAlchemyOutboxDomainEventPublisher(s, tenant).publish(
            whatsapp_event("msg-live-2")
        )
        s.commit()
    with session_factory() as s:
        jobs = SqlAlchemyOutboxWorkerStore(s).claim(10, "worker-live", 300)
        later = datetime.now(timezone.utc) + timedelta(seconds=120)
        SqlAlchemyOutboxWorkerStore(s).mark(jobs[0].event_id, DeliveryOutcome.RETRYABLE, next_attempt_at=later)
        s.commit()
        assert SqlAlchemyOutboxWorkerStore(s).claim(10, "worker-live", 300) == []


def whatsapp_event(message_id: str) -> WhatsAppMessageReceived:
    return WhatsAppMessageReceived(
        message_id=message_id,
        source_phone="+919000000008",
        text="180",
    )


def test_audit_events_are_append_only(postgres_ops_db):
    _, session_factory = postgres_ops_db
    tenant = _seed_tenant(session_factory, "audit-live")
    event_id = uuid4()

    with session_factory() as s:
        s.add(
            AuditEventModel(
                audit_event_id=event_id,
                tenant_id=tenant,
                actor_id=uuid4(),
                actor_type="system",
                action="CREATE",
                resource_type="integration.probe",
                resource_id=str(uuid4()),
                occurred_at=datetime.now(timezone.utc),
                outcome="SUCCESS",
            )
        )
        s.commit()

    with pytest.raises(Exception):
        with session_factory() as s:
            s.execute(
                text("UPDATE audit_events SET outcome = 'TAMPERED' WHERE audit_event_id = :eid"),
                {"eid": str(event_id)},
            )
            s.commit()

    with pytest.raises(Exception):
        with session_factory() as s:
            s.execute(
                text("DELETE FROM audit_events WHERE audit_event_id = :eid"),
                {"eid": str(event_id)},
            )
            s.commit()

    with session_factory() as s:
        rows = s.execute(
            text("SELECT outcome FROM audit_events WHERE audit_event_id = :eid"),
            {"eid": str(event_id)},
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "SUCCESS"


def test_channel_tenant_resolver_postgres(postgres_ops_db):
    _, session_factory = postgres_ops_db
    tenant = _seed_tenant(session_factory, "route-live")
    phone = "+919000000009"
    patient_id = uuid4()

    with SqlAlchemyUnitOfWork(session_factory, tenant) as uow:
        uow.patients.add(
            Patient(
                id=patient_id,
                uh_id=UHID("UH-ROUTE"),
                name="Routed Patient",
                phone=PhoneNumber(phone),
            )
        )
        uow.commit()

    with session_factory() as s:
        resolved = SqlAlchemyChannelTenantResolver(s).resolve(phone)
        assert resolved is not None
        assert resolved.tenant_id == tenant
        assert resolved.patient_id == patient_id


def test_channel_tenant_resolver_no_cross_phone_leakage(postgres_ops_db):
    _, session_factory = postgres_ops_db
    tenant = _seed_tenant(session_factory, "route-leak")
    phone_a = "+919000000010"
    phone_b = "+919000000011"
    patient_a = uuid4()
    patient_b = uuid4()

    with SqlAlchemyUnitOfWork(session_factory, tenant) as uow:
        uow.patients.add(
            Patient(
                id=patient_a,
                uh_id=UHID("UH-LEAK-A"),
                name="Patient A",
                phone=PhoneNumber(phone_a),
            )
        )
        uow.patients.add(
            Patient(
                id=patient_b,
                uh_id=UHID("UH-LEAK-B"),
                name="Patient B",
                phone=PhoneNumber(phone_b),
            )
        )
        uow.commit()

    with session_factory() as s:
        resolver = SqlAlchemyChannelTenantResolver(s)
        resolved_b = resolver.resolve(phone_b)
        assert resolved_b is not None
        assert resolved_b.patient_id == patient_b
        # Regression: input phone must NOT be shadowed by a matching column so
        # that an unrelated number (e.g. the newest patient) never answers.
        resolved_a = resolver.resolve(phone_a)
        assert resolved_a is not None
        assert resolved_a.patient_id == patient_a
        assert resolver.resolve("+919000000099") is None


__all__ = [
    "test_idempotency_lifecycle_and_concurrency",
    "test_webhook_receipt_dedup_on_postgres",
    "test_outbox_claim_mark_lease",
    "test_audit_events_are_append_only",
    "test_channel_tenant_resolver_postgres",
    "test_channel_tenant_resolver_no_cross_phone_leakage",
]