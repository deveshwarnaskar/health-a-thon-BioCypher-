# Gate 10P-C Implementation Report: Database Reliability, Pooling, Backup & PITR

## Executive Summary

**Gate 10P-C (Database Reliability, Pooling, Backup & PITR)** hardens the production database tier for the THALI + P.L.A.T.E. system. This gate establishes production-grade connection pooling, deterministic session and transaction boundaries, resilient worker database access, dynamic migration configuration, bounded readiness probes, automated backup and recovery tooling with cryptographic verification, and a comprehensive Point-in-Time Recovery (PITR) architecture.

All changes strictly preserve existing domain models, tenant boundaries, Row-Level Security (RLS) policies, clinical authority rules, and the transactional outbox architecture without creating duplicate backends or second authorization paths.

---

## 1. Baseline & Branch Verification

- **Frozen Baseline Tag:** `gate-10p-b-security-hardening-sealed`
- **Parent Commit SHA:** `4e59f5e5ec7576d47411962a8ee82eb03eb6a403`
- **Implementation Branch:** `feature/gate-10p-c-database-reliability`
- **Lineage Verification:** Directly branched from `gate-10p-b-security-hardening-sealed` with no intermediary commits.
- **Sealing Rule Adherence:** No seal tags (`gate-10p-c-*-sealed`) have been created during implementation. The branch remains open pending independent audit.

---

## 2. Architecture & Implementation Changes

### 2.1 SQLAlchemy Connection Pooling Architecture
In `config/settings.py` and `backend/infrastructure/config/database.py`, connection pooling settings are explicitly defined and enforced:
- **`pool_size` (default: 5, ge=1):** Configures baseline persistent connections per process.
- **`max_overflow` (default: 10, ge=0):** Configures surge capacity above baseline pool size.
- **`pool_timeout` (default: 5.0s, range: 0.5s–60.0s):** Enforces a fast-fail bounded timeout when the pool is exhausted, preventing client requests from hanging indefinitely.
- **`pool_recycle` (default: 3600s):** Automatically recycles connections older than 1 hour to prevent stale connections from database-side idle timeouts or firewall state resets.
- **`pool_pre_ping` (default: True):** Issues a lightweight test probe (`SELECT 1`) on connection checkout to verify liveness, transparently replacing disconnected sockets without bubbling errors to request handlers.
- **`pool_reset_on_return` (default: `"rollback"`):** Enforces an explicit rollback on connection return to the pool, ensuring uncommitted transactions or session-level state are never leaked to subsequent requests.
- **SQLite In-Memory Isolation:** Retains `StaticPool` with `check_same_thread=False` for `:memory:` SQLite during unit tests.

### 2.2 HTTP Session & Engine Lifecycle
In `backend/interfaces/http/dependencies.py`:
- Connection pooling parameters from `Settings().database` are wired into `_get_engine(db_url)`.
- `_session_factory_cache` caches `sessionmaker[Session]` instances per `db_url`, eliminating the overhead of recreating session factories per HTTP request.
- `get_unit_of_work()` and `get_ops_session()` utilize `_get_session_factory(db_url)`, ensuring clean session boundaries and transaction-local RLS (`is_local=true`).
- `reset_config_cache()` cleans up cached engines and session factories between test runs.

### 2.3 Worker Session Hardening
In `backend/infrastructure/persistence/ops/tenant_resolver.py` and `backend/interfaces/cli/worker.py`:
- **Eliminated Long-Lived System Session:** Previously, `build_worker()` created a single `system_session` passed into `SqlAlchemyChannelTenantResolver`, making the worker vulnerable to connection drops, transaction poisoning, or memory bloat.
- **Short-Lived Resolver Sessions:** `SqlAlchemyChannelTenantResolver` now accepts a `session_factory` (or legacy session for backwards compatibility) and opens an isolated, short-lived session per lookup.
- **Exception Isolation & Rollback:** On any lookup exception, the resolver rolls back and closes the session, preventing poisoned transaction states from impacting subsequent intake messages.

### 2.4 Dynamic Alembic Migration URL Resolution
In `backend/infrastructure/persistence/alembic/env.py`:
- Implemented `_get_database_url()` to dynamically prioritize:
  1. `THALI_DATABASE__URL` environment variable.
  2. `Settings().database.url` from application settings.
  3. Alembic INI configuration (`sqlalchemy.url`) or fallback.
- Updated `run_migrations_offline()` and `run_migrations_online()` to use `_get_database_url()`.
- Guarded `context.config` access and migration execution so importing `env.py` in test suites does not trigger migration runs or fail when outside Alembic CLI context.

### 2.5 Bounded Database Readiness Health Checks
In `backend/infrastructure/config/database.py`:
- `check_database_health(engine, timeout_seconds=3.0)` executes `SELECT 1` with a query timeout and wraps the call in a `ThreadPoolExecutor`.
- Explicitly calls `executor.shutdown(wait=False, cancel_futures=True)` on completion or timeout, guaranteeing that hung connections return `False` within the timeout window without blocking the probe thread.

### 2.6 Backup & Restore Tooling
Implemented production-grade shell scripts in `scripts/`:
- **`scripts/backup_database.sh`:**
  - Performs `pg_dump --no-owner --no-privileges --clean --if-exists` with `gzip -9` compression.
  - Automatically generates a companion `.sha256` checksum file.
  - Generates ISO 8601 UTC timestamped filenames (`thali_backup_YYYYMMDD_HHMMSSZ.sql.gz`).
  - Implements fail-closed error handling (`set -euo pipefail`), traps temporary files on interrupt, and sanitizes database credentials from logs.
- **`scripts/restore_database.sh`:**
  - Requires explicit `--confirm` flag to guard against accidental production database overwrites.
  - Verifies the companion `.sha256` checksum prior to initiating restore, aborting immediately on corruption or mismatch.
  - Decompresses and pipes the SQL dump directly into `psql` within a managed recovery session.

---

## 3. Point-in-Time Recovery (PITR) & WAL Archiving Architecture

For production PostgreSQL deployments in Gate 10P-C, Point-in-Time Recovery (PITR) provides continuous data protection and recovery to any arbitrary second:

```
                          Continuous WAL Archiving
  PostgreSQL Primary ───► pg_receivewal / archive_command ───► Immutable S3/GCS Bucket
        │                                                               │
        │ (Daily Base Backup)                                          │
        ▼                                                               ▼
  pg_dump / pg_basebackup ──► Encrypted Storage ────────────────► PITR Restoration
```

### 3.1 PostgreSQL Engine WAL Configuration
In `postgresql.conf`:
```ini
wal_level = replica
archive_mode = on
archive_command = 'envdir /etc/wal-e.d/env wal-g wal-push %p' # or cloud-native equivalent
archive_timeout = 300 # forces WAL switch every 5 minutes to bound RPO
```

### 3.2 Recovery Target Parameters
To restore to a specific point in time:
```sql
-- In recovery.signal:
restore_command = 'wal-g wal-fetch %f %p'
recovery_target_time = '2026-09-18 04:30:00 UTC'
recovery_target_action = 'promote'
```

### 3.3 Recovery Metrics
- **RPO (Recovery Point Objective):** <= 5 minutes (enforced by `archive_timeout = 300` and continuous WAL streaming).
- **RTO (Recovery Time Objective):** <= 30 minutes for databases up to 100 GB using compressed base backup restoration and parallel WAL replay.

---

## 4. Test Matrix & Verification Evidence

All 11 mandatory Gate 10P-C test cases are implemented and verified in `tests/integration/test_gate_10p_c_database_reliability.py`:

| Test ID | Description | Component Verified | Result |
|---|---|---|---|
| **TC-10PC-01** | Database Readiness Timeout Bounding | `check_database_health()` returns `False` within bounded time when DB hangs | **PASS** |
| **TC-10PC-02** | QueuePool Parameter Enforcement | `create_db_engine()` configures `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle` | **PASS** |
| **TC-10PC-03** | Pool Exhaustion Fast-Fail | Connection requests block only up to `pool_timeout` (0.5s) then raise `TimeoutError` | **PASS** |
| **TC-10PC-04** | Stale Connection Reconnect (`pool_pre_ping`) | Dropped/stale socket is detected and transparently reconnected on checkout | **PASS** |
| **TC-10PC-05** | Transaction Rollback Determinism | Failed transaction rolls back completely without committing uncommitted writes | **PASS** |
| **TC-10PC-06** | Pooled Connection Tenant State Isolation | Reused pooled connection resets session state; RLS strictly fails-closed across tenants | **PASS** |
| **TC-10PC-07** | Dependency Injection Session Factory Reuse | HTTP dependencies cache session factories and inject pooled engines | **PASS** |
| **TC-10PC-08** | Worker Session Lifecycle & Fault Recovery | Worker tenant resolver uses short-lived sessions and recovers immediately after errors | **PASS** |
| **TC-10PC-09** | Alembic Dynamic URL Resolution | Alembic `env.py` prioritizes `THALI_DATABASE__URL` and `Settings().database.url` | **PASS** |
| **TC-10PC-10** | Backup Script Generation & Checksum Integrity | `backup_database.sh` produces valid `.sql.gz` and `.sha256` checksum file | **PASS** |
| **TC-10PC-11** | Restore Script Safety Guard & Checksum Check | `restore_database.sh` rejects execution without `--confirm` and verifies SHA-256 | **PASS** |

### Live PostgreSQL Integration Test Execution
In addition to SQLite unit tests, live PostgreSQL 17 integration tests verified:
1. `test_tc10pc_06_rls_isolation_across_reused_pooled_connection`: Created temporary table with RLS enabled and forced, inserted records under Tenant 1, reused connection from a size-1 pool, and verified Tenant 2 and unauthenticated queries see 0 rows.
2. `test_tc10pc_10_and_11_backup_restore_cycle`: Backed up a live PostgreSQL database via `scripts/backup_database.sh`, verified checksum, dropped table, restored via `scripts/restore_database.sh`, and validated data integrity.

---

## 5. Monorepo Regression Verification

Full test suites across the entire repository were executed cleanly:

- **Backend Pytest Suite:**
  - `uv run pytest`
  - **Result:** `821 passed, 818 warnings in 31.83s` (100% passing across domain, application, infrastructure, API, RLS, and integration suites).
- **Admin Web App:**
  - `pnpm --dir apps/admin-web test`
  - **Result:** `5 test files passed, 41 tests passed in 1.68s`.
  - `pnpm --dir apps/admin-web build`
  - **Result:** Vite production build succeeded (`dist/index.html`, gzip bundle generated).
- **Mobile App:**
  - `pnpm --dir apps/mobile typecheck`: **Clean (0 errors)**.
  - `pnpm --dir apps/mobile lint`: **Clean (0 errors)**.
  - `pnpm --dir apps/mobile test`: **37 test files passed, 373 tests passed**.
  - `pnpm --dir apps/mobile test:component`: **18 test suites passed, 126 tests passed**.
  - `pnpm --dir apps/mobile export --platform android`: **Bundle succeeded (1507 modules, Hermes bytecode generated)**.

---

## 6. Deferred Scope Boundaries

The following areas are explicitly deferred to future production gates:
- **Gate 10P-D:** Observability, OpenTelemetry, Prometheus metrics, structured audit logs.
- **Gate 10P-E:** Physical mobile device release builds, app store signing, and distribution profiles.
- **Gate 10P-F:** Chaos engineering, fault-injection tests, and full scale load testing.
- **Gate 10P-G:** Cloud infrastructure provisioning, Terraform/IaC, multi-region failover, and go-live.

---

## 7. Audit Readiness Confirmation

All implementation requirements for Gate 10P-C have been met:
- [x] Code branched from sealed Gate 10P-B parent.
- [x] SQLAlchemy pooling configured with fail-closed bounds and pre-ping.
- [x] Session and transaction boundaries strictly enforced; RLS isolation verified on pooled connection reuse.
- [x] Worker database session decoupled from worker lifecycle.
- [x] Dynamic Alembic migration database URL resolution in place.
- [x] Health check timeout bounded and non-blocking.
- [x] Automated backup and restore scripts with SHA-256 validation created.
- [x] WAL/PITR architecture documented.
- [x] All 11 test cases passed.
- [x] Zero regressions across backend, admin-web, and mobile.
- [x] No sealed tag created.

**STATUS: READY FOR INDEPENDENT AUDIT**
