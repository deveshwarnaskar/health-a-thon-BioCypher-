"""Gate 09 — unit tests: idempotency fingerprint + relational stores."""

from __future__ import annotations

from uuid import uuid4
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.application.ops.contracts import DeliveryOutcome, WebhookReceipt
from backend.infrastructure.persistence.models import Base
from backend.infrastructure.persistence.ops.idempotency_store import SqlAlchemyIdempotencyStore
from backend.infrastructure.persistence.ops.outbox_store import SqlAlchemyOutboxWorkerStore
from backend.infrastructure.persistence.ops.replay_store import SqlAlchemyWebhookReceiptStore
from backend.interfaces.http.ops.idempotency import build_fingerprint


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = Session(engine)
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


class TestFingerprint:
    def test_deterministic_for_same_input(self):
        a = build_fingerprint(method="POST", path="/x", raw_body=b'{"a":1}', secret="s")
        b = build_fingerprint(method="POST", path="/x", raw_body=b'{"a":1}', secret="s")
        assert a == b
        assert len(a) == 64

    def test_sensitive_to_body(self):
        a = build_fingerprint(method="POST", path="/x", raw_body=b'{"a":1}', secret="s")
        b = build_fingerprint(method="POST", path="/x", raw_body=b'{"a":2}', secret="s")
        assert a != b

    def test_sensitive_to_path_secret(self):
        base = lambda body: build_fingerprint(method="POST", path="/x", raw_body=body, secret="s")
        assert base(b"1") != build_fingerprint(method="POST", path="/y", raw_body=b"1", secret="s")
        assert base(b"1") != build_fingerprint(method="POST", path="/x", raw_body=b"1", secret="t")


class TestIdempotencyStore:
    def test_reserve_then_complete_then_replay(self, session):
        store = SqlAlchemyIdempotencyStore(session)
        tenant, actor, key = uuid4(), uuid4(), "k1"
        fp = "abc"
        r1 = store.reserve(tenant, actor, key, fp)
        assert r1.accepted
        session.commit()

        store.complete(tenant, actor, key, 201, {"X-A": "1"}, '{"id": 42}')
        session.commit()

        r2 = store.reserve(tenant, actor, key, fp)
        assert not r2.accepted
        assert r2.replay
        assert r2.status_code == 201
        assert r2.body == '{"id": 42}'

    def test_fingerprint_mismatch_conflicts(self, session):
        store = SqlAlchemyIdempotencyStore(session)
        tenant, actor, key = uuid4(), uuid4(), "k-mismatch"
        assert store.reserve(tenant, actor, key, "fp-a").accepted
        session.commit()
        result = store.reserve(tenant, actor, key, "fp-b")
        assert not result.accepted
        assert result.conflict == "mismatch"

    def test_in_progress_conflict(self, session):
        store = SqlAlchemyIdempotencyStore(session)
        tenant, actor, key = uuid4(), uuid4(), "k-inflight"
        assert store.reserve(tenant, actor, key, "fp").accepted
        session.commit()
        result = store.reserve(tenant, actor, key, "fp")
        assert result.conflict == "in_progress"

    def test_release_failed_clears_reservation(self, session):
        store = SqlAlchemyIdempotencyStore(session)
        tenant, actor, key = uuid4(), uuid4(), "k-release"
        assert store.reserve(tenant, actor, key, "fp").accepted
        session.commit()
        store.release_failed(tenant, actor, key)
        session.commit()
        fresh = store.reserve(tenant, actor, key, "fp")
        assert fresh.accepted

    def test_keys_are_scoped_by_tenant_and_actor(self, session):
        store = SqlAlchemyIdempotencyStore(session)
        tenant = uuid4()
        a1, a2 = uuid4(), uuid4()
        assert store.reserve(tenant, a1, "same", "fp").accepted
        session.commit()
        assert store.reserve(tenant, a2, "same", "fp").accepted
        other_tenant = uuid4()
        assert store.reserve(other_tenant, a1, "same", "fp").accepted


class TestWebhookReceiptStore:
    def _receipt(self, pkey: str) -> WebhookReceipt:
        return WebhookReceipt(
            receipt_id=uuid4(),
            provider="whatsapp",
            provider_message_id=pkey,
            event_type="message_received",
            received_at=datetime.now(timezone.utc),
            source_phone="+919000000001",
        )

    def test_fresh_then_duplicate(self, session):
        store = SqlAlchemyWebhookReceiptStore(session)
        pkey = "provider-msg-1"
        assert store.record(self._receipt(pkey)) is True
        session.commit()
        assert store.record(self._receipt(pkey)) is False

    def test_distinct_ids_are_fresh(self, session):
        store = SqlAlchemyWebhookReceiptStore(session)
        a = store.record(self._receipt("a"))
        b = store.record(self._receipt("b"))
        session.commit()
        assert a is True and b is True


class TestOutboxWorkerStore:
    def _publish_intake(self, session, pkey: str) -> None:
        from backend.domain.events.channel import WhatsAppMessageReceived
        from backend.infrastructure.persistence.uow.outbox_publisher import (
            SqlAlchemyOutboxDomainEventPublisher,
        )

        publisher = SqlAlchemyOutboxDomainEventPublisher(session, tenant_id=None)
        event = WhatsAppMessageReceived(message_id=pkey, source_phone="+919000000001", text="180")
        publisher.publish(event)
        session.commit()

    def test_claim_mark_published(self, session):
        self._publish_intake(session, "m-1")
        store = SqlAlchemyOutboxWorkerStore(session)
        jobs = store.claim(10, "worker-1", 300)
        assert len(jobs) == 1
        assert jobs[0].event_type == "whatsapp.message.received"
        store.mark(jobs[0].event_id, DeliveryOutcome.SUCCESS)
        assert store.claim(10, "worker-1", 300) == []

    def test_transient_marks_retry_with_next_attempt(self, session):
        from datetime import timedelta

        self._publish_intake(session, "m-2")
        store = SqlAlchemyOutboxWorkerStore(session)
        job = store.claim(10, "worker-1", 300)[0]
        later = datetime.now(timezone.utc) + timedelta(seconds=10)
        store.mark(job.event_id, DeliveryOutcome.RETRYABLE, next_attempt_at=later)
        assert store.claim(10, "worker-1", 300) == []  # not due until the backoff deadline

    def test_claim_orders_all_due_jobs(self, session):
        for i in range(3):
            self._publish_intake(session, f"m-{i}")
        store = SqlAlchemyOutboxWorkerStore(session)
        jobs = store.claim(5, "worker-1", 300)
        assert len(jobs) == 3