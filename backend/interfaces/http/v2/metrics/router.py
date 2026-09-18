"""Prometheus metrics HTTP exposition endpoint (Gate 10P-D).

Exposes the Prometheus text exposition format (version 0.0.4).
Implements configurable network boundary protection / access token enforcement
to ensure operational telemetry is not publicly exposed without authorization.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from config.settings import Settings
from backend.infrastructure.observability.metrics import get_metrics_registry

metrics_router = APIRouter()

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _is_loopback_or_internal(client_host: str | None) -> bool:
    """Check whether caller IP is loopback or trusted internal boundary."""
    if not client_host:
        return False
    return client_host in {"127.0.0.1", "::1", "localhost", "testclient"}


@metrics_router.get("/metrics", include_in_schema=False, tags=["Observability"])
async def metrics_endpoint(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    x_metrics_key: str | None = Header(None, alias="X-Metrics-Key"),
) -> Response:
    """Scrape endpoint for Prometheus collectors."""
    settings = Settings()

    # Protected boundary check (Gate 10P-D §19)
    if settings.observability.metrics_require_auth:
        client_ip = request.client.host if request.client else None
        is_internal = _is_loopback_or_internal(client_ip)

        token = x_metrics_key
        if not token and authorization and authorization.startswith("Bearer "):
            token = authorization[7:].strip()

        configured_token = settings.observability.metrics_auth_token
        auth_valid = bool(configured_token and token == configured_token)

        if not (is_internal or auth_valid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Metrics endpoint is restricted to authorized internal scrapers",
            )

    registry = get_metrics_registry()
    exposition = registry.generate_exposition()
    return Response(content=exposition, media_type=PROMETHEUS_CONTENT_TYPE)
