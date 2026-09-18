"""Gate 09 — Transactional outbox worker orchestration.

The worker is a pure application-layer executor:

1. ``OutboxWorkerStore.claim`` leases up to N due rows (postgres uses
   ``FOR UPDATE SKIP LOCKED``; the store owns the dialect details).
2. Each job is dispatched to the handler registered for its ``event_type``.
3. Handlers return a ``DeliveryOutcome``; the worker drives the state machine
   (PUBLISHED / retry-with-exponential-backoff / DEAD_LETTER).

Failed executions follow the service's retry budget: transient failures are
re-scheduled with exponential backoff (2s → 4s → 8s → 16s) and a job whose
retry count reaches the budget is moved to ``DEAD_LETTER``. Crash recovery is
handled at the store layer via lease expiry (Gate 09 §13.2, §16.2).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping

from backend.domain.exceptions import DomainError

from .contracts import OUTBOX_MAX_RETRIES, DeliveryOutcome, OutboxJob
from .errors import PermanentWorkerFailure, TransientWorkerError
from .ports import OutboxWorkerStore, WorkerTelemetryPort

logger = logging.getLogger(__name__)

# The registry maps event_type → handler callable. A handler MUST traverse the
# application command handlers; it is forbidden from mutating tables directly.
EventHandler = Callable[[OutboxJob], DeliveryOutcome]


class OutboxWorker:
    """Polling executor for transactional outbox jobs."""

    def __init__(
        self,
        store: OutboxWorkerStore,
        handlers: Mapping[str, EventHandler],
        *,
        worker_id: str = "outbox-worker",
        claim_limit: int = 10,
        lease_seconds: int = 300,
        max_retries: int = OUTBOX_MAX_RETRIES,
        telemetry: WorkerTelemetryPort | None = None,
    ) -> None:
        self._store = store
        self._handlers = dict(handlers)
        self._worker_id = worker_id
        self._claim_limit = claim_limit
        self._lease_seconds = lease_seconds
        self._max_retries = max_retries
        self._telemetry = telemetry

    def process_once(self) -> int:
        """Claim and process one batch of due jobs. Returns the count claimed."""
        if self._telemetry:
            try:
                self._telemetry.on_worker_health(True)
            except Exception:
                pass

        jobs = self._store.claim(self._claim_limit, self._worker_id, self._lease_seconds)
        for job in jobs:
            self._process(job)

        if self._telemetry:
            try:
                self._telemetry.on_sync_activity("success")
            except Exception:
                pass

        return len(jobs)

    def _process(self, job: OutboxJob) -> None:
        start_time = time.perf_counter()
        span_ctx = None
        if self._telemetry:
            try:
                cid = str(job.correlation_id) if job.correlation_id else ""
                span_ctx = self._telemetry.on_job_started(job.event_type, cid)
            except Exception:
                pass

        handler = self._handlers.get(job.event_type)
        if handler is None:
            logger.warning("outbox event without a registered handler: %s", job.event_type)
            self._store.mark(job.event_id, DeliveryOutcome.SUCCESS)
            if self._telemetry:
                try:
                    duration = max(0.0, time.perf_counter() - start_time)
                    self._telemetry.on_job_finished(
                        job.event_type, "no_handler", duration, context=span_ctx
                    )
                except Exception:
                    pass
            return

        try:
            outcome = handler(job)
        except TransientWorkerError:
            outcome = DeliveryOutcome.RETRYABLE
        except (PermanentWorkerFailure, DomainError) as exc:
            logger.error("outbox job permanently failed: %s %s", job.event_type, exc)
            self._store.mark(job.event_id, DeliveryOutcome.PERMANENT, error=str(exc))
            if self._telemetry:
                try:
                    duration = max(0.0, time.perf_counter() - start_time)
                    self._telemetry.on_job_finished(
                        job.event_type,
                        "permanent_failure",
                        duration,
                        failure_type="domain_or_permanent",
                        context=span_ctx,
                    )
                except Exception:
                    pass
            return
        except Exception as exc:  # noqa: BLE001 - transport/unknown → retry
            logger.exception("outbox worker transient error for %s", job.event_type)
            self._store.mark(job.event_id, DeliveryOutcome.RETRYABLE, error=str(exc))
            if self._telemetry:
                try:
                    duration = max(0.0, time.perf_counter() - start_time)
                    self._telemetry.on_job_finished(
                        job.event_type,
                        "retryable",
                        duration,
                        failure_type="transport_error",
                        context=span_ctx,
                    )
                except Exception:
                    pass
            return

        duration = max(0.0, time.perf_counter() - start_time)
        if outcome is DeliveryOutcome.SUCCESS:
            self._store.mark(job.event_id, DeliveryOutcome.SUCCESS)
            if self._telemetry:
                try:
                    self._telemetry.on_job_finished(
                        job.event_type, "success", duration, context=span_ctx
                    )
                except Exception:
                    pass
            return

        if outcome is DeliveryOutcome.PERMANENT:
            self._store.mark(
                job.event_id, DeliveryOutcome.PERMANENT, error="handler reported permanent failure"
            )
            if self._telemetry:
                try:
                    self._telemetry.on_job_finished(
                        job.event_type,
                        "permanent_failure",
                        duration,
                        failure_type="handler_permanent",
                        context=span_ctx,
                    )
                except Exception:
                    pass
            return

        # RETRYABLE → exponential backoff or dead-letter at the budget ceiling.
        attempts_so_far = job.retry_count + 1
        if attempts_so_far >= self._max_retries:
            self._store.mark(
                job.event_id, DeliveryOutcome.PERMANENT, error="retry budget exhausted"
            )
            if self._telemetry:
                try:
                    self._telemetry.on_job_finished(
                        job.event_type,
                        "dead_letter",
                        duration,
                        failure_type="budget_exhausted",
                        context=span_ctx,
                    )
                except Exception:
                    pass
            return

        delay_seconds = retry_backoff_seconds(attempts_so_far + 1)
        self._store.mark(
            job.event_id,
            DeliveryOutcome.RETRYABLE,
            next_attempt_at=retry_backoff_deadline(delay_seconds),
        )
        if self._telemetry:
            try:
                self._telemetry.on_job_finished(
                    job.event_type, "retryable", duration, context=span_ctx
                )
            except Exception:
                pass


def retry_backoff_seconds(attempt: int) -> int:
    """Exponential backoff for a scheduled attempt number (Gate 09 §16.2).

    Attempt 1 executes immediately; every later attempt waits 2^(n-1) seconds
    (2s, 4s, 8s, 16s...). Attempts never exceed the 5-retry budget.
    """
    if attempt <= 1:
        return 0
    return 2 ** (attempt - 1)


def retry_backoff_deadline(delay_seconds: int):
    """Timezone-aware UTC timestamp ``delay_seconds`` from now (None when zero)."""
    if not delay_seconds:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)