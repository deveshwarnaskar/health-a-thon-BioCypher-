"""Prometheus-compatible operational metrics registry (Gate 10P-D).

Thread-safe, dependency-free implementation of Prometheus text exposition format 0.0.4.
Enforces strict low-cardinality label rules and forbids PHI / tenant identifiers in labels.
Provides pre-registered metric collectors for HTTP, Database, Worker, Outbox, and Dependencies.
"""

from __future__ import annotations

import logging
import math
import re
import threading
from collections import Counter as PyCounter, defaultdict
from enum import Enum
from typing import Any, Mapping, Sequence

logger = logging.getLogger(__name__)

# Non-negotiable PHI & high-cardinality label blocklist (Gate 10P-D §4 & §8)
FORBIDDEN_LABEL_KEYS: frozenset[str] = frozenset(
    {
        "patient_id",
        "patient",
        "tenant_id",
        "tenant",
        "user_id",
        "user",
        "uh_id",
        "body",
        "payload",
        "message",
        "phone",
        "token",
        "secret",
        "jwt",
        "authorization",
        "password",
        "glucose",
        "medication",
        "carbs",
        "glycemic_index",
        "correlation_id",
        "request_id",
        "request_body",
    }
)

_VALID_NAME_RE = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_VALID_LABEL_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

DEFAULT_HISTOGRAM_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
)


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


def _validate_label_keys(labels: Mapping[str, str]) -> None:
    for k in labels:
        if not _VALID_LABEL_NAME_RE.match(k):
            raise ValueError(f"Invalid Prometheus label name: '{k}'")
        if k.lower() in FORBIDDEN_LABEL_KEYS:
            raise ValueError(
                f"Forbidden label key '{k}' violates Gate 10P-D PHI / low-cardinality policy"
            )


def _format_labels(labels: Mapping[str, str]) -> str:
    if not labels:
        return ""
    items = []
    for k in sorted(labels.keys()):
        val = str(labels[k]).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        items.append(f'{k}="{val}"')
    return "{" + ",".join(items) + "}"


class CounterMetric:
    """Thread-safe Prometheus Counter."""

    def __init__(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = tuple(label_names)
        self._values: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, delta: float = 1.0, **labels: str) -> None:
        if delta < 0:
            raise ValueError("Counters can only be incremented by non-negative amounts")
        _validate_label_keys(labels)
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            self._values[key] += delta

    def get(self, **labels: str) -> float:
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            return self._values.get(key, 0.0)

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            if not self._values:
                lines.append(f"{self.name} 0")
            else:
                for key, val in sorted(self._values.items()):
                    label_str = _format_labels(dict(key))
                    val_str = f"{int(val)}" if val.is_integer() else f"{val:.4f}"
                    lines.append(f"{self.name}{label_str} {val_str}")
        return lines


class GaugeMetric:
    """Thread-safe Prometheus Gauge."""

    def __init__(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = tuple(label_names)
        self._values: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def set(self, value: float, **labels: str) -> None:
        _validate_label_keys(labels)
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            self._values[key] = float(value)

    def inc(self, delta: float = 1.0, **labels: str) -> None:
        _validate_label_keys(labels)
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            self._values[key] += float(delta)

    def dec(self, delta: float = 1.0, **labels: str) -> None:
        _validate_label_keys(labels)
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            self._values[key] -= float(delta)

    def get(self, **labels: str) -> float:
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            return self._values.get(key, 0.0)

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} gauge",
        ]
        with self._lock:
            if not self._values:
                lines.append(f"{self.name} 0")
            else:
                for key, val in sorted(self._values.items()):
                    label_str = _format_labels(dict(key))
                    val_str = f"{int(val)}" if val.is_integer() else f"{val:.4f}"
                    lines.append(f"{self.name}{label_str} {val_str}")
        return lines


class HistogramMetric:
    """Thread-safe Prometheus Histogram with cumulative buckets, sum, and count."""

    def __init__(
        self,
        name: str,
        help_text: str,
        label_names: Sequence[str] = (),
        buckets: Sequence[float] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> None:
        self.name = name
        self.help_text = help_text
        self.label_names = tuple(label_names)
        self.buckets = tuple(sorted(buckets))
        self._counts: dict[tuple[tuple[str, str], ...], int] = defaultdict(int)
        self._sums: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._bucket_counts: dict[tuple[tuple[str, str], ...], dict[float, int]] = defaultdict(
            lambda: {b: 0 for b in self.buckets}
        )
        self._lock = threading.Lock()

    def observe(self, value: float, **labels: str) -> None:
        _validate_label_keys(labels)
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        val = float(value)
        with self._lock:
            self._counts[key] += 1
            self._sums[key] += val
            b_counts = self._bucket_counts[key]
            for b in self.buckets:
                if val <= b:
                    b_counts[b] += 1

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            if not self._counts:
                # Emit zero base histogram
                for b in self.buckets:
                    lines.append(f'{self.name}_bucket{{le="{b}"}} 0')
                lines.append(f'{self.name}_bucket{{le="+Inf"}} 0')
                lines.append(f"{self.name}_sum 0.0")
                lines.append(f"{self.name}_count 0")
            else:
                for key, total_count in sorted(self._counts.items()):
                    base_labels = dict(key)
                    b_counts = self._bucket_counts[key]
                    for b in self.buckets:
                        lbls = dict(base_labels)
                        lbls["le"] = str(b)
                        lines.append(f"{self.name}_bucket{_format_labels(lbls)} {b_counts[b]}")
                    # +Inf bucket equals total count
                    inf_lbls = dict(base_labels)
                    inf_lbls["le"] = "+Inf"
                    lines.append(f"{self.name}_bucket{_format_labels(inf_lbls)} {total_count}")
                    sum_val = self._sums[key]
                    lines.append(f"{self.name}_sum{_format_labels(base_labels)} {sum_val:.4f}")
                    lines.append(f"{self.name}_count{_format_labels(base_labels)} {total_count}")
        return lines


class PrometheusMetricsRegistry:
    """Central Prometheus Metrics Registry implementing exposition format 0.0.4."""

    def __init__(self) -> None:
        self._counters: dict[str, CounterMetric] = {}
        self._gauges: dict[str, GaugeMetric] = {}
        self._histograms: dict[str, HistogramMetric] = {}
        self._lock = threading.RLock()
        self._init_standard_metrics()

    def _init_standard_metrics(self) -> None:
        """Register the baseline production metric catalog (Gate 10P-D §8)."""
        # 1. HTTP Metrics
        self.register_counter(
            "http_requests_total",
            "Total count of HTTP requests processed by method, normalized route, and status class",
            label_names=["method", "route", "status_class"],
        )
        self.register_histogram(
            "http_request_duration_seconds",
            "HTTP request processing duration in seconds by method and normalized route",
            label_names=["method", "route"],
        )
        self.register_counter(
            "http_request_failures_total",
            "Total count of failed HTTP requests (4xx and 5xx) by route and error code",
            label_names=["method", "route", "error_code"],
        )

        # 2. Database Metrics
        self.register_gauge(
            "db_pool_size",
            "Configured persistent base connection pool size",
        )
        self.register_gauge(
            "db_pool_checked_out",
            "Number of active connections currently checked out from the pool",
        )
        self.register_gauge(
            "db_pool_checked_in",
            "Number of idle available connections currently in the pool",
        )
        self.register_gauge(
            "db_pool_overflow",
            "Number of active overflow connections above base pool size",
        )
        self.register_counter(
            "db_pool_timeouts_total",
            "Count of connection checkout timeout events (exhaustion indicator)",
        )
        self.register_counter(
            "db_pool_connection_failures_total",
            "Count of database connection errors and failed pre-pings",
        )
        self.register_gauge(
            "db_readiness_status",
            "Database readiness probe outcome (1 = ready, 0 = unavailable)",
        )
        self.register_gauge(
            "db_backup_last_success_timestamp_seconds",
            "Epoch timestamp in seconds of the most recent successful database backup",
        )

        # 3. Worker Metrics
        self.register_counter(
            "worker_jobs_processed_total",
            "Total count of outbox worker jobs processed by event type and outcome",
            label_names=["event_type", "outcome"],
        )
        self.register_counter(
            "worker_jobs_failed_total",
            "Total count of outbox worker job failures by event type and failure classification",
            label_names=["event_type", "failure_type"],
        )
        self.register_counter(
            "worker_job_retries_total",
            "Total count of outbox job retry reschedules by event type",
            label_names=["event_type"],
        )
        self.register_histogram(
            "worker_job_duration_seconds",
            "Outbox worker job execution duration in seconds by event type",
            label_names=["event_type"],
        )
        self.register_gauge(
            "worker_health_status",
            "Outbox worker operational heartbeat state (1 = healthy/polling, 0 = stalled)",
        )

        # 4. Outbox Metrics
        self.register_gauge(
            "outbox_pending_depth",
            "Current count of pending due events in transactional outbox queue",
        )
        self.register_gauge(
            "outbox_processing_depth",
            "Current count of leased in-flight events in transactional outbox queue",
        )
        self.register_gauge(
            "outbox_dead_letter_depth",
            "Current count of exhausted dead-letter events in transactional outbox queue",
        )
        self.register_counter(
            "outbox_sync_activity_total",
            "Outbox batch synchronization occurrences by outcome",
            label_names=["outcome"],
        )

        # 5. Dependency Metrics
        self.register_gauge(
            "dependency_health_status",
            "Health status of external dependencies (1 = healthy, 0 = unavailable)",
            label_names=["dependency"],
        )
        self.register_counter(
            "dependency_failures_total",
            "Count of operational failures observed when contacting dependencies",
            label_names=["dependency", "error_type"],
        )
        self.register_counter(
            "whatsapp_deliveries_total",
            "Outbound WhatsApp message delivery outcomes",
            label_names=["outcome"],
        )
        self.register_counter(
            "ai_generation_requests_total",
            "AI generation request outcomes",
            label_names=["outcome"],
        )

        # 6. Multimodal AI Metrics (voice/image WhatsApp ingestion)
        self.register_counter(
            "sarvam_requests_total",
            "Sarvam provider request outcomes by operation and result",
            label_names=["operation", "result"],
        )
        self.register_histogram(
            "sarvam_request_latency_seconds",
            "Sarvam provider request latency by operation",
            label_names=["operation"],
        )
        self.register_counter(
            "sarvam_errors_total",
            "Sarvam provider failures by error class",
            label_names=["error_class"],
        )
        self.register_counter(
            "sarvam_timeouts_total",
            "Sarvam provider timeout events by operation",
            label_names=["operation"],
        )
        self.register_counter(
            "sarvam_rate_limits_total",
            "Sarvam provider HTTP 429 rate-limit events",
        )
        self.register_counter(
            "sarvam_stt_success_total",
            "Saaras speech-to-text successes",
        )
        self.register_counter(
            "sarvam_stt_failure_total",
            "Saaras speech-to-text failures",
        )
        self.register_counter(
            "sarvam_translation_success_total",
            "Sarvam translation successes",
        )
        self.register_counter(
            "sarvam_translation_failure_total",
            "Sarvam translation failures",
        )
        self.register_counter(
            "sarvam_tts_success_total",
            "Sarvam text-to-speech successes",
        )
        self.register_counter(
            "sarvam_tts_failure_total",
            "Sarvam text-to-speech failures",
        )
        self.register_counter(
            "image_analysis_success_total",
            "Image meal analysis successes (provider-neutral)",
        )
        self.register_counter(
            "image_analysis_failure_total",
            "Image meal analysis failures (provider-neutral)",
        )
        self.register_counter(
            "voice_pipeline_success_total",
            "WhatsApp voice pipeline outcomes by stage",
            label_names=["kind"],
        )
        self.register_counter(
            "voice_pipeline_failure_total",
            "WhatsApp voice pipeline failures by reason",
            label_names=["kind"],
        )
        self.register_counter(
            "image_pipeline_success_total",
            "WhatsApp image pipeline outcomes by stage",
            label_names=["kind"],
        )
        self.register_counter(
            "image_pipeline_failure_total",
            "WhatsApp image pipeline failures by reason",
            label_names=["kind"],
        )
        self.register_counter(
            "multimodal_pipeline_failures_total",
            "Multimodal pipeline safe-fallback failures by reason",
            label_names=["kind"],
        )
        self.register_counter(
            "multimodal_confirmation_success_total",
            "Multimodal meal drafts confirmed by patient",
        )
        self.register_counter(
            "multimodal_confirmation_cancel_total",
            "Multimodal meal drafts cancelled/rejected by patient",
        )

    def register_counter(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> CounterMetric:
        with self._lock:
            if name in self._counters:
                return self._counters[name]
            metric = CounterMetric(name, help_text, label_names)
            self._counters[name] = metric
            return metric

    def register_gauge(self, name: str, help_text: str, label_names: Sequence[str] = ()) -> GaugeMetric:
        with self._lock:
            if name in self._gauges:
                return self._gauges[name]
            metric = GaugeMetric(name, help_text, label_names)
            self._gauges[name] = metric
            return metric

    def register_histogram(
        self,
        name: str,
        help_text: str,
        label_names: Sequence[str] = (),
        buckets: Sequence[float] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> HistogramMetric:
        with self._lock:
            if name in self._histograms:
                return self._histograms[name]
            metric = HistogramMetric(name, help_text, label_names, buckets)
            self._histograms[name] = metric
            return metric

    def counter(self, name: str, help_text: str = "", label_names: Sequence[str] = ()) -> CounterMetric:
        with self._lock:
            if name not in self._counters:
                self.register_counter(name, help_text or name, label_names)
            return self._counters[name]

    def gauge(self, name: str, help_text: str = "", label_names: Sequence[str] = ()) -> GaugeMetric:
        with self._lock:
            if name not in self._gauges:
                self.register_gauge(name, help_text or name, label_names)
            return self._gauges[name]

    def histogram(
        self,
        name: str,
        help_text: str = "",
        label_names: Sequence[str] = (),
        buckets: Sequence[float] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> HistogramMetric:
        with self._lock:
            if name not in self._histograms:
                self.register_histogram(name, help_text or name, label_names, buckets)
            return self._histograms[name]

    def generate_exposition(self) -> str:
        """Render all registered metrics into Prometheus text format 0.0.4."""
        lines: list[str] = []
        with self._lock:
            # Sorted by metric name for deterministic output
            all_metrics: list[Any] = []
            all_metrics.extend(self._counters.values())
            all_metrics.extend(self._gauges.values())
            all_metrics.extend(self._histograms.values())
            all_metrics.sort(key=lambda m: m.name)

            for m in all_metrics:
                lines.extend(m.render())
        # Prometheus format requires a trailing newline
        return "\n".join(lines) + "\n"

    def reset_all(self) -> None:
        """Reset all metrics to baseline state (useful between tests)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._init_standard_metrics()


# Global Singleton Registry
_GLOBAL_REGISTRY: PrometheusMetricsRegistry | None = None
_REGISTRY_LOCK = threading.Lock()


def get_metrics_registry() -> PrometheusMetricsRegistry:
    """Return the application global PrometheusMetricsRegistry."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        with _REGISTRY_LOCK:
            if _GLOBAL_REGISTRY is None:
                _GLOBAL_REGISTRY = PrometheusMetricsRegistry()
    return _GLOBAL_REGISTRY


# ==============================================================================
# Legacy Compatibility Boundary (Gate 09)
# ==============================================================================
class MetricsRegistry:
    """Thread-safe in-memory counter registry preserved for Gate 09 compatibility."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self._counters: PyCounter[str] = PyCounter()
        self._lock = threading.Lock()

    def increment(self, name: str, delta: int = 1) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._counters[name] += delta
            logger.debug("metrics counter %s += %s -> %s", name, delta, self._counters[name])

    def snapshot(self) -> Mapping[str, int]:
        with self._lock:
            return dict(self._counters)

    def emit(self) -> Mapping[str, int]:
        snapshot = self.snapshot()
        if self.enabled and snapshot:
            logger.info("gate09 metrics snapshot: %s", snapshot)
        return snapshot

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


__all__ = [
    "PrometheusMetricsRegistry",
    "CounterMetric",
    "GaugeMetric",
    "HistogramMetric",
    "get_metrics_registry",
    "MetricsRegistry",
    "FORBIDDEN_LABEL_KEYS",
]