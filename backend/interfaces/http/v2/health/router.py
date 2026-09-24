"""Health/readiness endpoints (Gate 07).

Liveness:  /health/live  — process alive.
Readiness: /health/ready — required dependencies ready enough for traffic.

Never leaks connection strings, credentials, internal traces, or PHI.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

health_router = APIRouter()


class LivenessResponse(BaseModel):
    status: str = "ok"


class ReadinessResponse(BaseModel):
    status: str
    checks: dict


@health_router.get("/health/live", response_model=LivenessResponse, tags=["Health"])
async def liveness() -> LivenessResponse:
    """Confirm the application process is alive."""
    return LivenessResponse(status="ok")


@health_router.get("/health/ready", response_model=ReadinessResponse, tags=["Health"])
async def readiness() -> ReadinessResponse:
    """Confirm required application dependencies are ready enough for traffic."""
    checks: dict = {"app": "ok"}

    try:
        from backend.infrastructure.config.database import check_database_health
        from backend.interfaces.http.dependencies import get_engine

        engine = get_engine()
        db_ok = check_database_health(engine)
        checks["database"] = "ok" if db_ok else "unavailable"
    except Exception:
        checks["database"] = "unavailable"

    try:
        from config.settings import Settings

        settings = Settings()
        if settings.redis.enabled:
            from backend.infrastructure.cache.redis_client import RedisCacheAdapter

            adapter = RedisCacheAdapter(
                host=settings.redis.host,
                port=settings.redis.port,
                password=settings.redis.password,
                db=settings.redis.db,
                fallback_in_memory=False,
                socket_timeout=1.0,
            )
            redis_ok = adapter.ping()
            checks["redis"] = "ok" if redis_ok else "unavailable"
    except Exception:
        checks["redis"] = "unavailable"

    if any(v != "ok" for v in checks.values()):
        return Response(
            content='{"status":"not_ready","checks":' + __import__("json").dumps(checks) + "}",
            media_type="application/json",
            status_code=503,
        )

    return ReadinessResponse(status="ok", checks=checks)