#!/bin/sh
set -e

# ==============================================================================
# THALI + P.L.A.T.E. FastAPI Application Entrypoint (Gate 10P-A)
# ==============================================================================
# Invariants:
# - Uses production ASGI server (Uvicorn) with application factory pattern.
# - Replaces shell with Uvicorn process (exec) for direct SIGTERM signal reception.
# - Graceful shutdown window defaults to 30 seconds.
# - No debug servers, no reload in production mode.
# ==============================================================================

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-2}"
LOG_LEVEL="${THALI_OBSERVABILITY__LOG_LEVEL:-INFO}"

# Map log level to lowercase for uvicorn compatibility
UVICORN_LOG_LEVEL=$(echo "${LOG_LEVEL}" | tr '[:upper:]' '[:lower:]')

echo "[entrypoint-api] Starting THALI API on ${HOST}:${PORT} (${WORKERS} worker(s), log_level=${UVICORN_LOG_LEVEL})..."

exec uvicorn "backend.interfaces.http.app:create_app" \
    --factory \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WORKERS}" \
    --log-level "${UVICORN_LOG_LEVEL}" \
    --timeout-graceful-shutdown 30
