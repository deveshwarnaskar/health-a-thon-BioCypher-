"""Observability infrastructure package (Gate 10P-D).

Integrates structured logging, Prometheus metrics, OpenTelemetry tracing,
and context propagation for correlation and request IDs.
"""

from .context import (
    correlation_id_ctx,
    get_correlation_id,
    get_request_id,
    request_id_ctx,
    set_correlation_id,
    set_request_id,
)
from .logging import (
    InfrastructureLogger,
    StructuredJsonFormatter,
    configure_logging,
    sanitize_exception,
    sanitize_log_dict,
)
from .metrics import (
    CounterMetric,
    FORBIDDEN_LABEL_KEYS,
    GaugeMetric,
    HistogramMetric,
    MetricsRegistry,
    MetricType,
    PrometheusMetricsRegistry,
    get_metrics_registry,
)
from .tracing import (
    ConsoleSpanExporter,
    FORBIDDEN_TRACE_ATTRS,
    InMemorySpanExporter,
    OtlpSpanExporter,
    Span,
    SpanContext,
    SpanExporter,
    SpanStatus,
    Tracer,
    TracerProvider,
    extract_trace_context,
    get_current_span,
    get_tracer,
    get_tracer_provider,
    inject_trace_context,
    sanitize_trace_attributes,
    set_tracer_provider,
)

__all__ = [
    # Context
    "correlation_id_ctx",
    "request_id_ctx",
    "get_correlation_id",
    "set_correlation_id",
    "get_request_id",
    "set_request_id",
    # Logging
    "InfrastructureLogger",
    "StructuredJsonFormatter",
    "configure_logging",
    "sanitize_log_dict",
    "sanitize_exception",
    # Metrics
    "PrometheusMetricsRegistry",
    "CounterMetric",
    "GaugeMetric",
    "HistogramMetric",
    "MetricType",
    "MetricsRegistry",
    "get_metrics_registry",
    "FORBIDDEN_LABEL_KEYS",
    # Tracing
    "SpanStatus",
    "SpanContext",
    "Span",
    "Tracer",
    "TracerProvider",
    "SpanExporter",
    "InMemorySpanExporter",
    "ConsoleSpanExporter",
    "OtlpSpanExporter",
    "get_current_span",
    "get_tracer_provider",
    "set_tracer_provider",
    "get_tracer",
    "extract_trace_context",
    "inject_trace_context",
    "sanitize_trace_attributes",
    "FORBIDDEN_TRACE_ATTRS",
]
