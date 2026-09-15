"""HTTP middleware: correlation IDs and security headers (Gate 07).

Correlation IDs are generated per-request (or accepted inbound if valid format).
Security headers are applied to all responses. No PHI in correlation IDs.
"""

from __future__ import annotations

import re
import uuid

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

CORRELATION_ID_HEADER = "X-Correlation-ID"
_SAFE_CORRELATION_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request/response cycle."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound = request.headers.get(CORRELATION_ID_HEADER, "")
        if inbound and _SAFE_CORRELATION_RE.match(inbound):
            correlation_id = inbound
        else:
            correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response


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
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationIDMiddleware)