"""OpenTelemetry-compatible tracing infrastructure (Gate 10P-D).

Provides lightweight, robust OpenTelemetry semantic tracing with strict PHI redaction,
W3C TraceContext propagation (traceparent), in-memory/console/OTLP export capabilities,
and fail-safe error boundaries ensuring tracing failures NEVER break business operations.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import secrets
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Generator, Mapping, Sequence

logger = logging.getLogger(__name__)

# Non-negotiable PHI & credential attribute blocklist (Gate 10P-D §4 & §15)
FORBIDDEN_TRACE_ATTRS: frozenset[str] = frozenset(
    {
        "patient_id",
        "patient",
        "tenant_id",
        "tenant",
        "user_id",
        "user",
        "doctor_id",
        "caregiver_id",
        "glucose",
        "glucose_value",
        "medication",
        "medication_plan",
        "carbs",
        "glycemic_index",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "client_secret",
        "api_key",
        "password",
        "authorization",
        "cookie",
        "request_body",
        "body",
        "payload",
        "message_body",
    }
)

_TRACEPARENT_RE = re.compile(
    r"^00-([0-9a-fA-F]{32})-([0-9a-fA-F]{16})-([0-9a-fA-F]{2})$"
)


class SpanStatus(str, Enum):
    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


class SpanContext:
    """W3C TraceContext immutable container."""

    def __init__(
        self,
        trace_id: str,
        span_id: str,
        trace_flags: str = "01",
        trace_state: str = "",
    ) -> None:
        self.trace_id = trace_id.lower()
        self.span_id = span_id.lower()
        self.trace_flags = trace_flags
        self.trace_state = trace_state

    @classmethod
    def generate(cls) -> SpanContext:
        trace_id = secrets.token_hex(16)  # 128-bit
        span_id = secrets.token_hex(8)    # 64-bit
        return cls(trace_id, span_id, "01")

    @classmethod
    def from_traceparent(cls, traceparent: str) -> SpanContext | None:
        match = _TRACEPARENT_RE.match(traceparent.strip())
        if not match:
            return None
        trace_id, span_id, trace_flags = match.groups()
        if trace_id == "0" * 32 or span_id == "0" * 16:
            return None
        return cls(trace_id, span_id, trace_flags)

    def to_traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"


def sanitize_trace_attributes(attrs: Mapping[str, Any]) -> dict[str, Any]:
    """Ensure no PHI or secrets are attached to trace attributes."""
    clean: dict[str, Any] = {}
    for k, v in attrs.items():
        k_lower = k.lower()
        if any(f in k_lower for f in FORBIDDEN_TRACE_ATTRS):
            continue
        # Truncate string attributes to prevent unbounded cardinality
        if isinstance(v, str):
            clean[k] = v[:256]
        elif isinstance(v, (int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)[:256]
    return clean


class Span:
    """OpenTelemetry Span representation."""

    def __init__(
        self,
        name: str,
        context: SpanContext,
        parent_context: SpanContext | None = None,
        attributes: Mapping[str, Any] | None = None,
        on_end: Callable[[Span], None] | None = None,
    ) -> None:
        self.name = name
        self.context = context
        self.parent_context = parent_context
        self.attributes: dict[str, Any] = sanitize_trace_attributes(attributes or {})
        self.events: list[dict[str, Any]] = []
        self.status = SpanStatus.UNSET
        self.status_description = ""
        self.start_time = time.time()
        self.end_time: float | None = None
        self.duration_ms: float = 0.0
        self._on_end = on_end
        self._ended = False
        self._lock = threading.Lock()

    def set_attribute(self, key: str, value: Any) -> Span:
        if self._ended:
            return self
        key_lower = key.lower()
        if any(f in key_lower for f in FORBIDDEN_TRACE_ATTRS):
            return self
        with self._lock:
            if isinstance(value, str):
                self.attributes[key] = value[:256]
            elif isinstance(value, (int, float, bool)):
                self.attributes[key] = value
            else:
                self.attributes[key] = str(value)[:256]
        return self

    def set_status(self, status: SpanStatus, description: str = "") -> Span:
        if self._ended:
            return self
        with self._lock:
            self.status = status
            self.status_description = description[:256]
        return self

    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> Span:
        if self._ended:
            return self
        safe_attrs = sanitize_trace_attributes(attributes or {})
        with self._lock:
            self.events.append(
                {
                    "name": name[:128],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "attributes": safe_attrs,
                }
            )
        return self

    def record_exception(self, exc: BaseException) -> Span:
        self.set_status(SpanStatus.ERROR, str(type(exc).__name__))
        self.add_event(
            "exception",
            {
                "exception.type": type(exc).__name__,
                "exception.message": str(exc)[:256],
            },
        )
        return self

    def end(self) -> None:
        if self._ended:
            return
        with self._lock:
            self._ended = True
            self.end_time = time.time()
            self.duration_ms = max(0.0, (self.end_time - self.start_time) * 1000.0)

        if self._on_end:
            try:
                self._on_end(self)
            except Exception:
                # Telemetry failure MUST NOT break business logic (Gate 10P-D §16)
                logger.debug("Span on_end callback failed safe")


# Current Span Context Tracking
_CURRENT_SPAN: ContextVar[Span | None] = ContextVar("current_span", default=None)


def get_current_span() -> Span | None:
    return _CURRENT_SPAN.get()


class SpanExporter:
    """Abstract base class for span exporters."""

    def export(self, spans: Sequence[Span]) -> None:
        raise NotImplementedError

    def shutdown(self) -> None:
        pass


class InMemorySpanExporter(SpanExporter):
    """Retains exported spans in memory for test verification."""

    def __init__(self) -> None:
        self._spans: list[Span] = []
        self._lock = threading.Lock()

    def export(self, spans: Sequence[Span]) -> None:
        with self._lock:
            self._spans.extend(spans)

    def get_finished_spans(self) -> list[Span]:
        with self._lock:
            return list(self._spans)

    def clear(self) -> None:
        with self._lock:
            self._spans.clear()


class ConsoleSpanExporter(SpanExporter):
    """Outputs finished spans to standard logging/console."""

    def export(self, spans: Sequence[Span]) -> None:
        for span in spans:
            logger.info(
                "TRACE span='%s' trace_id=%s span_id=%s duration=%.2fms status=%s attrs=%s",
                span.name,
                span.context.trace_id,
                span.context.span_id,
                span.duration_ms,
                span.status.value,
                span.attributes,
            )


class OtlpSpanExporter(SpanExporter):
    """OTLP HTTP/JSON span exporter with non-blocking error boundary."""

    def __init__(self, endpoint: str, timeout: float = 2.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def export(self, spans: Sequence[Span]) -> None:
        if not self.endpoint or not spans:
            return
        try:
            import httpx

            payload = {
                "resourceSpans": [
                    {
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": s.context.trace_id,
                                        "spanId": s.context.span_id,
                                        "parentSpanId": s.parent_context.span_id if s.parent_context else None,
                                        "name": s.name,
                                        "status": {"code": s.status.value},
                                        "attributes": [
                                            {"key": k, "value": {"stringValue": str(v)}}
                                            for k, v in s.attributes.items()
                                        ],
                                    }
                                    for s in spans
                                ]
                            }
                        ]
                    }
                ]
            }
            # Short-timeout POST to avoid blocking request loop
            with httpx.Client(timeout=self.timeout) as client:
                client.post(self.endpoint, json=payload)
        except Exception:
            # Safe degradation: exporter failure must never propagate
            logger.debug("OtlpSpanExporter delivery failed safe")


class Tracer:
    """Tracer creating spans under the active TracerProvider."""

    def __init__(self, name: str, provider: TracerProvider) -> None:
        self.name = name
        self.provider = provider

    def start_span(
        self,
        name: str,
        parent_context: SpanContext | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> Span:
        if parent_context is None:
            active_span = get_current_span()
            if active_span:
                parent_context = active_span.context

        if parent_context:
            context = SpanContext(
                trace_id=parent_context.trace_id,
                span_id=secrets.token_hex(8),
                trace_flags=parent_context.trace_flags,
            )
        else:
            context = SpanContext.generate()

        merged_attrs = {"service.name": self.provider.service_name}
        if attributes:
            merged_attrs.update(attributes)

        return Span(
            name=name,
            context=context,
            parent_context=parent_context,
            attributes=merged_attrs,
            on_end=self.provider.on_span_end,
        )

    @contextlib.contextmanager
    def start_as_current_span(
        self,
        name: str,
        parent_context: SpanContext | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        span = self.start_span(name, parent_context=parent_context, attributes=attributes)
        token = _CURRENT_SPAN.set(span)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise
        finally:
            span.end()
            _CURRENT_SPAN.reset(token)


class TracerProvider:
    """Central registry and lifecycle manager for tracing."""

    def __init__(
        self,
        service_name: str = "thali-plate",
        exporter: SpanExporter | None = None,
    ) -> None:
        self.service_name = service_name
        self.exporter = exporter or InMemorySpanExporter()
        self._tracers: dict[str, Tracer] = {}
        self._lock = threading.Lock()

    def get_tracer(self, name: str = "default") -> Tracer:
        with self._lock:
            if name not in self._tracers:
                self._tracers[name] = Tracer(name, self)
            return self._tracers[name]

    def on_span_end(self, span: Span) -> None:
        if self.exporter:
            try:
                self.exporter.export([span])
            except Exception:
                logger.debug("Span export failed safe")


# Global TracerProvider Singleton
_GLOBAL_TRACER_PROVIDER: TracerProvider | None = None
_PROVIDER_LOCK = threading.Lock()


def get_tracer_provider() -> TracerProvider:
    global _GLOBAL_TRACER_PROVIDER
    if _GLOBAL_TRACER_PROVIDER is None:
        with _PROVIDER_LOCK:
            if _GLOBAL_TRACER_PROVIDER is None:
                _GLOBAL_TRACER_PROVIDER = TracerProvider()
    return _GLOBAL_TRACER_PROVIDER


def set_tracer_provider(provider: TracerProvider) -> None:
    global _GLOBAL_TRACER_PROVIDER
    with _PROVIDER_LOCK:
        _GLOBAL_TRACER_PROVIDER = provider


def get_tracer(name: str = "default") -> Tracer:
    return get_tracer_provider().get_tracer(name)


def extract_trace_context(headers: Mapping[str, str]) -> SpanContext | None:
    """Extract W3C traceparent from inbound HTTP headers."""
    # Case-insensitive lookup
    traceparent = None
    for k, v in headers.items():
        if k.lower() == "traceparent":
            traceparent = v
            break
    if not traceparent:
        return None
    return SpanContext.from_traceparent(traceparent)


def inject_trace_context(headers: dict[str, str], span: Span) -> None:
    """Inject W3C traceparent into outbound HTTP headers."""
    headers["traceparent"] = span.context.to_traceparent()


__all__ = [
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
