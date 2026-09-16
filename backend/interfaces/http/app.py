"""FastAPI application factory (Gate 07).

Creates the HTTP application with:
- API v2 routing
- Security dependencies
- Exception handlers
- CORS configuration
- Security headers
- Request-size protection
- Correlation IDs
- Health endpoints
- OpenAPI configuration
- No business logic in routes
"""

from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import Settings
from backend.interfaces.http.errors import register_exception_handlers
from backend.interfaces.http.middleware import register_middleware
from backend.interfaces.http.v2.router import api_v2_router
from backend.interfaces.http.v2.health.router import health_router

MAX_REQUEST_BODY_BYTES = 8 * 1024 * 1024  # 8 MiB


def enforce_request_size(content_length: str | None) -> JSONResponse | None:
    """Apply request-size protection.

    Returns a safe error response when the declared Content-Length is
    malformed or exceeds the limit; otherwise returns None.
    """
    if content_length is None:
        return None
    try:
        size = int(content_length)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_CONTENT_LENGTH", "message": "Malformed Content-Length header"}},
        )
    if size > MAX_REQUEST_BODY_BYTES:
        return JSONResponse(
            status_code=413,
            content={"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Request body too large"}},
        )
    return None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = Settings()

    app = FastAPI(
        title="THALI P.L.A.T.E. API",
        version=settings.app.version,
        docs_url="/api/v2/docs" if settings.app.env != "production" else None,
        redoc_url="/api/v2/redoc" if settings.app.env != "production" else None,
        openapi_url="/api/v2/openapi.json" if settings.app.env != "production" else None,
    )

    original_openapi = app.openapi

    def _openapi() -> dict:
        schema = original_openapi()
        if settings.app.env != "production":
            schema.setdefault("components", {}).setdefault("securitySchemes", {})[
                "bearerAuth"
            ] = {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Gate 06/07 verified HS256 JWT (Authorization: Bearer <token>)",
            }
        return schema

    app.openapi = _openapi  # type: ignore[method-assign]

    # CORS: explicit origins, NEVER "*" with credentials.
    allowed_origins = settings.security.allowed_origins or ["http://localhost:3000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
        max_age=600,
    )

    # Request-size protection (applies to every route incl. webhook + JSON API)
    @app.middleware("http")
    async def _request_size_limit(request: Request, call_next: Callable):
        error = enforce_request_size(request.headers.get("content-length"))
        if error is not None:
            return error
        return await call_next(request)

    # Idempotency-key middleware (Gate 09). Added FIRST so it sits beneath the
    # correlation/security middleware: outer layers still stamp headers on the
    # responses it short-circuits (replay / 409 / 400).
    from backend.interfaces.http.ops.idempotency import IdempotencyMiddleware

    app.add_middleware(
        IdempotencyMiddleware,
        secret=settings.identity.client_secret or "dev-secret-change-in-production",
    )

    # Middleware: correlation IDs + security headers
    register_middleware(app)

    # Safe global exception handlers
    register_exception_handlers(app)

    # Routers: all business endpoints under /api/v2; health outside.
    app.include_router(api_v2_router, prefix="/api/v2")
    app.include_router(health_router)

    return app