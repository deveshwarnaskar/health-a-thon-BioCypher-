"""HTTP middleware: correlation IDs and security headers (Gate 07).

Correlation IDs are generated per-request (or accepted inbound if valid format).
Security headers are applied to all responses. No PHI in correlation IDs.
"""

from __future__ import annotations

import re
import uuid

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.infrastructure.observability.context import (
    correlation_id_ctx,
    request_id_ctx,
)

CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_CORRELATION_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request/response cycle."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound = request.headers.get(CORRELATION_ID_HEADER, "")
        if inbound and _SAFE_CORRELATION_RE.match(inbound):
            correlation_id = inbound
        else:
            correlation_id = str(uuid.uuid4())

        request_id_inbound = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = (
            request_id_inbound
            if request_id_inbound and _SAFE_CORRELATION_RE.match(request_id_inbound)
            else correlation_id
        )

        request.state.correlation_id = correlation_id
        request.state.request_id = request_id

        token_cid = correlation_id_ctx.set(correlation_id)
        token_rid = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            correlation_id_ctx.reset(token_cid)
            request_id_ctx.reset(token_rid)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply security headers to all responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store"
        return response


def register_middleware(app: FastAPI) -> None:
    """Register middleware on the FastAPI application."""
    from .observability import HttpObservabilityMiddleware

    # Starlette executes middlewares in reverse order of addition (LIFO):
    # SecurityHeadersMiddleware (outermost) -> CorrelationIDMiddleware -> HttpObservabilityMiddleware -> App
    app.add_middleware(HttpObservabilityMiddleware)
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)