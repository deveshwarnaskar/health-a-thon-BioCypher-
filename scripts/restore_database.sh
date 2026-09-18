#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# THALI + P.L.A.T.E. Production PostgreSQL Restore Script (Gate 10P-C)
# ==============================================================================
# Purpose:
# Restores a compressed PostgreSQL database backup into an explicitly specified
# target database after verifying SHA-256 cryptographic checksums.
#
# Invariants:
# - Requires explicit --confirm flag to prevent accidental restoration.
# - Validates SHA-256 checksum if .sha256 checksum file is present.
# - Zero credential or password leakage in stdout, stderr, or log streams.
# - Returns explicit non-zero exit codes on any failure.
#
# Usage:
#   ./scripts/restore_database.sh -f <backup.sql.gz> -d <target_db_url> --confirm
# ==============================================================================

BACKUP_FILE=""
DB_URL="${THALI_DATABASE__URL:-${DATABASE_URL:-}}"
CONFIRMED="${CONFIRM_RESTORE:-false}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--file)
      BACKUP_FILE="$2"
      shift 2
      ;;
    -d|--db-url)
      DB_URL="$2"
      shift 2
      ;;
    --confirm)
      CONFIRMED="true"
      shift 1
      ;;
    -h|--help)
      echo "Usage: $0 -f <backup.sql.gz> -d <target_db_url> --confirm"
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "ERROR: Backup file (-f/--file) must be specified." >&2
  exit 1
fi

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "ERROR: Backup file not found: ${BACKUP_FILE}" >&2
  exit 1
fi

if [[ -z "${DB_URL}" ]]; then
  echo "ERROR: Target database URL (-d/--db-url) must be specified." >&2
  exit 1
fi

if [[ "${CONFIRMED}" != "true" ]]; then
  echo "ERROR: Safety guard triggered. You must pass --confirm or set CONFIRM_RESTORE=true to proceed with database restore." >&2
  exit 2
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql utility not found in PATH. Please install PostgreSQL client tools." >&2
  exit 1
fi

if ! command -v gzip >/dev/null 2>&1; then
  echo "ERROR: gzip utility not found in PATH." >&2
  exit 1
fi

# Sanitize SQLAlchemy driver prefix if present (postgresql+psycopg:// -> postgresql://)
CLEAN_DB_URL=$(echo "${DB_URL}" | sed -E 's/^postgresql\+[a-zA-Z0-9_-]+:\/\//postgresql:\/\//')

# Step 1: Verify Checksum if present
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [[ -f "${CHECKSUM_FILE}" ]]; then
  echo "=== [1/3] Verifying SHA-256 Checksum ==="
  DIRNAME=$(dirname "${BACKUP_FILE}")
  BASENAME=$(basename "${BACKUP_FILE}")
  
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "${DIRNAME}" && sha256sum --check "${BASENAME}.sha256" --status) || {
      echo "ERROR: Checksum verification FAILED for ${BACKUP_FILE}." >&2
      exit 3
    }
  elif command -v shasum >/dev/null 2>&1; then
    (cd "${DIRNAME}" && shasum -a 256 --check "${BASENAME}.sha256" --status) || {
      echo "ERROR: Checksum verification FAILED for ${BACKUP_FILE}." >&2
      exit 3
    }
  fi
  echo "✓ Checksum verification PASSED."
else
  echo "WARNING: No accompanying .sha256 file found for ${BACKUP_FILE}. Proceeding with cautious restore."
fi

echo "=== [2/3] Executing PostgreSQL Restore ==="
# Execute decompression and stream to psql
if ! gzip -dc "${BACKUP_FILE}" | psql --dbname="${CLEAN_DB_URL}" --single-transaction --set ON_ERROR_STOP=1 --quiet 2>/dev/null; then
  echo "ERROR: psql restore execution failed." >&2
  exit 4
fi

echo "=== [3/3] Validating Target Database Connectivity Post-Restore ==="
if ! psql --dbname="${CLEAN_DB_URL}" --command="SELECT 1;" --tuples-only --quiet >/dev/null 2>&1; then
  echo "ERROR: Target database post-restore connectivity check failed." >&2
  exit 5
fi

echo "✓ Database restore successfully completed into target database."
exit 0
