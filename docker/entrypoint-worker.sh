#!/bin/sh
set -e

# ==============================================================================
# THALI Transactional Outbox Worker Entrypoint (Gate 10P-A)
# ==============================================================================
# Invariants:
# - Invokes existing worker entrypoint: backend.interfaces.cli.worker
# - Runs in continuous poll mode with configurable interval.
# - Replaces shell with Python process (exec) for direct SIGTERM signal reception.
# - Cleanly releases leases on worker termination.
# ==============================================================================

INTERVAL="${WORKER_POLL_INTERVAL:-5.0}"

echo "[entrypoint-worker] Starting THALI Transactional Outbox Worker (poll_interval=${INTERVAL}s)..."

exec python -m backend.interfaces.cli.worker --poll --interval "${INTERVAL}"
