"""Gate 09 — unit tests: outbox worker orchestration and retry policy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from backend.application.ops.contracts import DeliveryOutcome, OutboxJob
from backend.application.ops.errors import (
    PermanentWorkerFailure,
    TransientWorkerError,
)
from backend.application.ops.worker import OutboxWorker, retry_backoff_deadline, retry_backoff_seconds


def _job(event_type: str = "test.event", retry_count: int = 0) -> OutboxJob:
    return OutboxJob(
        event_id=uuid4(),
        event_type=event_type,
        tenant_id=UUID(int=1),
        patient_id=UUID(int=2),
        correlation_id=UUID(int=3),
        payload={},
        occurred_at=datetime.now(timezone.utc),
        retry_count=retry_count,
    )


class FakeWorkerStore:
    def __init__(self, jobs: list[OutboxJob]) -> None:
        self.jobs = list(jobs)
        self.marked: list[tuple[UUID, DeliveryOutcome, dict]] = []
        self.claims = 0

    def claim(self, limit: int, worker_id: str, lease_seconds: int) -> list[OutboxJob]:
        self.claims += 1
        jobs = self.jobs[:limit]
        self.jobs = self.jobs[limit:]
        return jobs

    def mark(self, event_id: UUID, outcome: DeliveryOutcome, *, error: str | None = None, next_attempt_at=None) -> None:
        self.marked.append((event_id, outcome, {"error": error, "next": next_attempt_at}))


class TestRetryBackoff:
    def test_attempt_one_is_immediate(self):
        assert retry_backoff_seconds(1) == 0
        assert retry_backoff_deadline(0) is None

    def test_attempt_schedule_is_exponential(self):
        assert [retry_backoff_seconds(n) for n in range(1, 7)] == [0, 2, 4, 8, 16, 32]

    def test_deadline_is_aware_utc(self):
        deadline = retry_backoff_deadline(4)
        assert deadline is not None
        assert deadline.tzinfo is not None
        delta = deadline - datetime.now(timezone.utc)
        assert timedelta(seconds=3) <= delta <= timedelta(seconds=5)


class TestOutboxWorker:
    def test_unknown_event_type_is_acked(self):
        store = FakeWorkerStore([_job(event_type="nobody.registered")])
        worker = OutboxWorker(store, {})
        assert worker.process_once() == 1
        outcome = store.marked[0][1]
        assert outcome is DeliveryOutcome.SUCCESS

    def test_success_handler_marks_published(self):
        store = FakeWorkerStore([_job()])
        worker = OutboxWorker(store, {"test.event": lambda job: DeliveryOutcome.SUCCESS})
        worker.process_once()
        assert store.marked[0][1] is DeliveryOutcome.SUCCESS

    def test_transient_failure_is_retryable_with_backoff(self):
        store = FakeWorkerStore([_job()])
        worker = OutboxWorker(store, {"test.event": lambda job: (_ for _ in ()).throw(TransientWorkerError())})
        worker.process_once()
        event_id, outcome, meta = store.marked[0]
        assert outcome is DeliveryOutcome.RETRYABLE
        assert meta["next"] is not None
        assert timedelta(seconds=1) <= (meta["next"] - datetime.now(timezone.utc)) <= timedelta(seconds=3)

    def test_permanent_failure_is_dead_lettered(self):
        store = FakeWorkerStore([_job()])
        worker = OutboxWorker(
            store,
            {"test.event": lambda job: (_ for _ in ()).throw(PermanentWorkerFailure())},
        )
        worker.process_once()
        assert store.marked[0][1] is DeliveryOutcome.PERMANENT

    def test_handler_reported_permanent_is_dead_lettered(self):
        store = FakeWorkerStore([_job()])
        worker = OutboxWorker(store, {"test.event": lambda job: DeliveryOutcome.PERMANENT})
        worker.process_once()
        assert store.marked[0][1] is DeliveryOutcome.PERMANENT

    def test_retry_budget_exhaustion_dead_letters(self):
        store = FakeWorkerStore([_job(retry_count=4)])
        worker = OutboxWorker(
            store,
            {"test.event": lambda job: (_ for _ in ()).throw(TransientWorkerError())},
            max_retries=5,
        )
        worker.process_once()
        event_id, outcome, meta = store.marked[0]
        assert outcome is DeliveryOutcome.PERMANENT
        assert meta["error"] == "retry budget exhausted"

    def test_unknown_exception_is_retryable(self):
        store = FakeWorkerStore([_job()])
        worker = OutboxWorker(store, {"test.event": lambda job: (_ for _ in ()).throw(RuntimeError("boom"))})
        worker.process_once()
        assert store.marked[0][1] is DeliveryOutcome.RETRYABLE