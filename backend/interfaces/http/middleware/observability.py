"""HTTP observability middleware (Gate 10P-D).

Instruments HTTP requests at the application boundary for:
- Normalized route template resolution (preventing metric cardinality explosions)
- OpenTelemetry span creation and W3C traceparent propagation
- Prometheus request count, latency histogram, and failure counters
- Machine-readable structured access logging with correlation ID
- Safe degradation (telemetry failure NEVER disrupts client responses)
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match

from backend.infrastructure.observability.context import get_correlation_id
from backend.infrastructure.observability.metrics import get_metrics_registry
from backend.infrastructure.observability.tracing import (
    SpanStatus,
    extract_trace_context,
    get_tracer,
)

logger = logging.getLogger("thali.http.observability")


def resolve_normalized_route(request: Request) -> str:
    """Resolve a low-cardinality route template (e.g. '/api/v2/patients/{patient_id}').

    Never returns raw path containing dynamic IDs or patient/tenant identifiers.
    """
    # 1. Direct route object in scope if matched
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return route.path

    # 2. Match against application routes if route is not yet populated
    app = request.app
    if hasattr(app, "routes"):
        for r in app.routes:
            match, _ = r.matches(request.scope)
            if match == Match.FULL and hasattr(r, "path"):
                return r.path

    # 3. Known static root endpoints
    path = request.url.path
    if path in {"/health/live", "/health/ready", "/metrics"}:
        return path

    return "unmatched"


class HttpObservabilityMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware collecting low-cardinality metrics and traces."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        tracer = get_tracer("http")

        # 1. Trace Context Extraction
        parent_context = extract_trace_context(dict(request.headers))
        span_name = f"HTTP {request.method}"

        # 2. Begin Span with safe initial attributes
        with tracer.start_as_current_span(
            span_name,
            parent_context=parent_context,
            attributes={"http.method": request.method},
        ) as span:
            status_code = 500
            try:
                response = await call_next(request)
                status_code = response.status_code
                return response
            except Exception as exc:
                span.record_exception(exc)
                raise
            finally:
                duration_sec = max(0.0, time.perf_counter() - start_time)
                duration_ms = duration_sec * 1000.0

                # 3. Safe Telemetry Recording (Fail-Safe Boundary)
                try:
                    route_template = resolve_normalized_route(request)
                    status_class = f"{status_code // 100}xx"

                    # Update Span attributes
                    span.name = f"HTTP {request.method} {route_template}"
                    span.set_attribute("http.route", route_template)
                    span.set_attribute("http.status_code", status_code)
                    span.set_attribute("http.status_class", status_class)
                    if status_code >= 500:
                        span.set_status(SpanStatus.ERROR, f"HTTP_{status_code}")
                    else:
                        span.set_status(SpanStatus.OK)

                    # Record Prometheus Metrics
                    registry = get_metrics_registry()
                    registry.counter("http_requests_total").inc(
                        method=request.method,
                        route=route_template,
                        status_class=status_class,
                    )
                    registry.histogram("http_request_duration_seconds").observe(
                        duration_sec,
                        method=request.method,
                        route=route_template,
                    )
                    if status_code >= 400:
                        registry.counter("http_request_failures_total").inc(
                            method=request.method,
                            route=route_template,
                            error_code=f"HTTP_{status_code}",
                        )

                    # Structured Access Log
                    cid = get_correlation_id()
                    log_extra = {
                        "event": "http_request_finished",
                        "method": request.method,
                        "route": route_template,
                        "status": status_code,
                        "duration_ms": duration_ms,
                        "correlation_id": cid,
                    }
                    if status_code >= 500:
                        logger.error("HTTP request error", extra=log_extra)
                    elif status_code >= 400:
                        logger.warning("HTTP request client error", extra=log_extra)
                    else:
                        logger.info("HTTP request completed", extra=log_extra)

                except Exception:
                    # Telemetry failure MUST NOT break business logic (Gate 10P-D §16)
                    logger.debug("HTTP observability telemetry failed safe")
