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

if [ "${THALI_SEED_ENABLED:-true}" = "true" ] || [ "${THALI_SEED_ENABLED:-true}" = "1" ]; then
    if [ -f "/app/scripts/seed_dev_stack.py" ] || [ -f "scripts/seed_dev_stack.py" ]; then
        echo "[entrypoint-migrate] Running dev stack seeder..."
        python -m scripts.seed_dev_stack
    else
        echo "[entrypoint-migrate] Seeder script not present; skipping seeding."
    fi
fi

