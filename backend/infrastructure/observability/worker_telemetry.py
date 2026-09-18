"""Worker telemetry adapter implementing WorkerTelemetryPort (Gate 10P-D).

Decoupled infrastructure adapter implementing the application WorkerTelemetryPort.
Ensures application-layer OutboxWorker has zero imports of backend.infrastructure.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.application.ops.ports import WorkerTelemetryPort
from .context import set_correlation_id
from .metrics import get_metrics_registry
from .tracing import Span, SpanStatus, get_tracer

logger = logging.getLogger("thali.worker.telemetry")


class WorkerTelemetryAdapter(WorkerTelemetryPort):
    """Concrete infrastructure adapter connecting worker lifecycle to Prometheus & OTel."""

    def __init__(self) -> None:
        self._registry = get_metrics_registry()
        self._tracer = get_tracer("worker")

    def on_worker_health(self, is_healthy: bool) -> None:
        try:
            self._registry.gauge("worker_health_status").set(1 if is_healthy else 0)
        except Exception:
            pass

    def on_sync_activity(self, outcome: str) -> None:
        try:
            self._registry.counter("outbox_sync_activity_total").inc(outcome=outcome)
        except Exception:
            pass

    def on_job_started(self, event_type: str, correlation_id: str) -> Any:
        try:
            set_correlation_id(correlation_id)
            span = self._tracer.start_span(
                f"worker.job {event_type}",
                attributes={"event_type": event_type},
            )
            return span
        except Exception:
            return None

    def on_job_finished(
        self,
        event_type: str,
        outcome: str,
        duration_sec: float,
        failure_type: str | None = None,
        context: Any = None,
    ) -> None:
        try:
            set_correlation_id("")
            span: Span | None = context if isinstance(context, Span) else None
            if span:
                if failure_type:
                    span.set_status(SpanStatus.ERROR, failure_type)
                else:
                    span.set_status(SpanStatus.OK)
                span.end()

            self._registry.counter("worker_jobs_processed_total").inc(
                event_type=event_type, outcome=outcome
            )
            self._registry.histogram("worker_job_duration_seconds").observe(
                duration_sec, event_type=event_type
            )
            if failure_type:
                self._registry.counter("worker_jobs_failed_total").inc(
                    event_type=event_type, failure_type=failure_type
                )
            if outcome == "retryable":
                self._registry.counter("worker_job_retries_total").inc(
                    event_type=event_type
                )
        except Exception:
            pass


__all__ = ["WorkerTelemetryAdapter"]
