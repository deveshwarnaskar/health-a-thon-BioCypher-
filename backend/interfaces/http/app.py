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

from config.settings import (
    SecurityConfigurationError,
    Settings,
    validate_security_configuration,
)
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


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    # Fail-closed validation of security and cryptographic invariants (Gate 10P-B)
    validate_security_configuration(settings)

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
                "description": (
                    "Keycloak-issued OIDC access token. Verified against the "
                    "configured trust boundary: RS256 via JWKS with issuer and "
                    "audience validation (HS256 accepted in development/testing "
                    "configurations only). Use Authorization: Bearer <token>."
                ),
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

    idempotency_secret = settings.identity.client_secret
    if not idempotency_secret:
        if settings.app.env == "production":
            raise SecurityConfigurationError(
                "Production environment requires identity.client_secret for idempotency HMAC."
            )
        idempotency_secret = "dev-secret-change-in-production"

    app.add_middleware(
        IdempotencyMiddleware,
        secret=idempotency_secret,
    )

    # Middleware: correlation IDs + security headers
    register_middleware(app)

    # Safe global exception handlers
    register_exception_handlers(app)

    # Routers: all business endpoints under /api/v2; health and metrics outside.
    from backend.interfaces.http.v2.metrics.router import metrics_router

    app.include_router(api_v2_router, prefix="/api/v2")
    app.include_router(health_router)
    app.include_router(metrics_router)

    # Observability initialization
    if settings.observability.structured_logs:
        from backend.infrastructure.observability.logging import configure_logging

        configure_logging(
            service=settings.observability.service_name,
            environment=settings.app.env,
            level=settings.observability.log_level,
            structured=True,
        )

    if settings.observability.tracing_enabled:
        from backend.infrastructure.observability.tracing import (
            ConsoleSpanExporter,
            InMemorySpanExporter,
            OtlpSpanExporter,
            TracerProvider,
            set_tracer_provider,
        )

        exporter_type = settings.observability.tracing_exporter.lower()
        if exporter_type == "otlp":
            exporter = OtlpSpanExporter(settings.observability.tracing_otlp_endpoint)
        elif exporter_type == "console":
            exporter = ConsoleSpanExporter()
        else:
            exporter = InMemorySpanExporter()

        set_tracer_provider(
            TracerProvider(
                service_name=settings.observability.service_name,
                exporter=exporter,
            )
        )

    return app