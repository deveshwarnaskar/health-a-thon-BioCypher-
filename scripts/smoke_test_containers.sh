#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Container Smoke Verification Script (Gate 10P-A)
# ==============================================================================
# Usage:
#   ./scripts/smoke_test_containers.sh
#
# Validates:
# - Compose configuration syntax
# - Image build (API, Worker, Migrate)
# - Rehearsal service startup and health
# - Migration execution to head
# - API liveness & readiness endpoints
# - Worker startup and process execution
# - Graceful shutdown
# ==============================================================================

echo "=== [1/6] Validating Docker Compose Configuration ==="
docker compose config --quiet
echo "✓ Compose configuration is valid."

echo "=== [2/6] Building Rehearsal Images (API, Worker, Migrate) ==="
docker compose build
echo "✓ All container targets built successfully."

echo "=== [3/6] Starting Infrastructure Services (PostgreSQL, Redis, MinIO) ==="
docker compose up -d postgres redis minio
echo "Waiting for infrastructure dependencies to become healthy..."

echo "Waiting for PostgreSQL to be healthy..."
PG_ATTEMPTS=0
PG_MAX_ATTEMPTS=30
until [ "$(docker compose ps --format '{{.Health}}' postgres 2>/dev/null)" = "healthy" ]; do
    PG_ATTEMPTS=$((PG_ATTEMPTS + 1))
    if [ "${PG_ATTEMPTS}" -ge "${PG_MAX_ATTEMPTS}" ]; then
        echo "✗ PostgreSQL failed to become healthy."
        docker compose logs postgres
        docker compose down -v
        exit 1
    fi
    sleep 2
done
echo "✓ PostgreSQL is healthy."

echo "Waiting for Redis to be healthy..."
REDIS_ATTEMPTS=0
REDIS_MAX_ATTEMPTS=30
until [ "$(docker compose ps --format '{{.Health}}' redis 2>/dev/null)" = "healthy" ]; do
    REDIS_ATTEMPTS=$((REDIS_ATTEMPTS + 1))
    if [ "${REDIS_ATTEMPTS}" -ge "${REDIS_MAX_ATTEMPTS}" ]; then
        echo "✗ Redis failed to become healthy."
        docker compose logs redis
        docker compose down -v
        exit 1
    fi
    sleep 2
done
echo "✓ Redis is healthy."

echo "Waiting for MinIO to respond on port 9000..."
MINIO_ATTEMPTS=0
MINIO_MAX_ATTEMPTS=30
until curl -s -f http://localhost:9000/minio/health/live > /dev/null 2>&1; do
    MINIO_ATTEMPTS=$((MINIO_ATTEMPTS + 1))
    if [ "${MINIO_ATTEMPTS}" -ge "${MINIO_MAX_ATTEMPTS}" ]; then
        echo "✗ MinIO failed to respond on /minio/health/live after ${MINIO_MAX_ATTEMPTS} attempts."
        docker compose logs minio
        docker compose down -v
        exit 1
    fi
    sleep 2
done
echo "✓ MinIO is responsive and healthy."
echo "✓ PostgreSQL, Redis, and MinIO are healthy."

echo "=== [4/6] Executing Deterministic Database Migrations ==="
docker compose run --rm migrate
echo "✓ Alembic migrations completed successfully."

echo "=== [5/6] Starting API and Worker Containers ==="
docker compose up -d api worker

echo "Waiting for API service to become ready..."
ATTEMPTS=0
MAX_ATTEMPTS=20
until curl -s -f http://localhost:8000/health/live > /dev/null 2>&1; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "${ATTEMPTS}" -ge "${MAX_ATTEMPTS}" ]; then
        echo "✗ API failed to respond to /health/live after ${MAX_ATTEMPTS} attempts."
        docker compose logs api
        docker compose down -v
        exit 1
    fi
    sleep 2
done

echo "Probing /health/live..."
LIVE_RESP=$(curl -s http://localhost:8000/health/live)
echo "Response: ${LIVE_RESP}"
if [[ "${LIVE_RESP}" != *"ok"* ]]; then
    echo "✗ Liveness check failed."
    docker compose down -v
    exit 1
fi
echo "✓ Liveness check PASSED."

echo "Probing /health/ready..."
READY_RESP=$(curl -s http://localhost:8000/health/ready)
echo "Response: ${READY_RESP}"
if [[ "${READY_RESP}" != *"ok"* ]]; then
    echo "✗ Readiness check failed."
    docker compose down -v
    exit 1
fi
echo "✓ Readiness check PASSED."

echo "Verifying worker logs..."
WORKER_LOGS=$(docker compose logs worker | tail -n 20)
if [[ "${WORKER_LOGS}" == *"Starting THALI Transactional Outbox Worker"* ]]; then
    echo "✓ Worker process startup confirmed."
else
    echo "✗ Worker startup log pattern not found."
    docker compose logs worker
    docker compose down -v
    exit 1
fi

echo "=== [6/6] Graceful Container Shutdown & Volume Cleanup ==="
docker compose down -v
echo "✓ All rehearsal containers and volumes cleaned up."

echo "========================================================"
echo "✓ GATE 10P-A CONTAINER SMOKE TEST PASSED SUCCESSFULLY"
echo "========================================================"
