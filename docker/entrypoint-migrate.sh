#!/bin/sh
set -e

# ==============================================================================
# THALI Alembic Migration Runner Entrypoint (Gate 10P-A)
# ==============================================================================
# Invariants:
# - Deterministic database migration upgrade to HEAD.
# - Separated from API and worker startup to prevent multi-instance race conditions.
# - Validates current migration revision post-upgrade.
# ==============================================================================

echo "[entrypoint-migrate] Running Alembic migrations to head..."
alembic upgrade head

echo "[entrypoint-migrate] Migrations completed successfully. Current database state:"
alembic current
