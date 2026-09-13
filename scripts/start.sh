#!/usr/bin/env bash
# Render/web-service entrypoint: seed the demo data fast (DB only — chart PNGs
# and the PDF are rebuilt on demand from live day-log data) then serve.
#
# The demo and the server MUST share one SQLite file, so the DB path is fixed
# here and exported before anything starts (AAHAAR_DB env still wins).
set -euo pipefail

export AAHAAR_DB="${AAHAAR_DB:-aahaar.db}"
# Single-responder mode: the deterministic AI intake worker answers every
# patient message (webhook is store-only & silent), so a patient never gets two
# texts for one message. Gemini is never wired to WhatsApp here.
export AAHAAR_AI_INTAKE="${AAHAAR_AI_INTAKE:-1}"
export AAHAAR_AI_ON_INBOUND="${AAHAAR_AI_ON_INBOUND:-0}"
python3 -m scripts.demo --days "${AAHAAR_DEMO_DAYS:-14}"
exec uvicorn app.server.main:app --host 0.0.0.0 --port "${PORT:-8000}"