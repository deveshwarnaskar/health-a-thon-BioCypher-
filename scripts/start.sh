#!/usr/bin/env bash
# Render/web-service entrypoint: seed the demo data fast (DB only — chart PNGs
# and the PDF are rebuilt on demand from live day-log data) then serve.
#
# The demo and the server MUST share one SQLite file, so the DB path is fixed
# here and exported before anything starts (AAHAAR_DB env still wins).
set -euo pipefail

export AAHAAR_DB="${AAHAAR_DB:-aahaar.db}"
python3 -m scripts.demo --days "${AAHAAR_DEMO_DAYS:-14}"
exec uvicorn app.server.main:app --host 0.0.0.0 --port "${PORT:-8000}"