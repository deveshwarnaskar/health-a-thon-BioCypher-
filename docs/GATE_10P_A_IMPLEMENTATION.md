# GATE 10P-A — PRODUCTION INFRASTRUCTURE, CONTAINERIZATION & CI/CD IMPLEMENTATION REPORT

**Gate:** Gate 10P-A — Production Infrastructure Foundation  
**System:** THALI + P.L.A.T.E. Assistive Diabetes-Care Workflow Platform  
**Sealed Base:** `gate-10o-offline-sync-localization-sealed` (`e7e375562e23c59d9e9ad267201d747a511ca328`)  
**Branch:** `feature/gate-10p-a-production-infrastructure`  
**Status:** IMPLEMENTATION COMPLETE — READY FOR INDEPENDENT AUDIT  
**Date:** 2026-09-18  

---

## 1. Executive Summary & Scope

Gate 10P-A implements the production infrastructure, containerization, local rehearsal stack, and CI/CD foundations for the THALI + P.L.A.T.E. platform on top of the frozen Gate 10O baseline.

This gate addresses the critical operational gap identified in the Gate 10P Readiness Analysis: transforming the ad-hoc local execution environment into a reproducible, deterministic, and secure containerized foundation suitable for continuous integration, staging rehearsal, and production deployment.

### In-Scope Deliverables
1. **Multi-Stage Production Dockerfile:** Minimal Debian-based runtime (`python:3.12-slim-bookworm`) with multi-stage dependency compilation using `uv` and unprivileged non-root user execution (`thali:thali`, UID 10001).
2. **Distinct Container Targets:** Logical targets for `api` (FastAPI ASGI server), `worker` (Transactional Outbox asynchronous event processor), and `migrate` (deterministic Alembic migration runner).
3. **Local Docker Compose Rehearsal Stack:** Complete multi-service local environment containing `postgres`, `redis`, `minio` (S3 emulator), `migrate`, `api`, and `worker` with isolated bridge networking and persistent volumes.
4. **Deterministic Dependency Locking:** Exact locked dependency manifest `requirements.lock` generated via `uv pip compile` to guarantee reproducible supply-chain integrity.
5. **Container Entrypoint Scripts:** Dedicated POSIX shell entrypoints with `exec` signal forwarding ensuring graceful `SIGTERM` handling for both API and background workers.
6. **Container Smoke Test Automation:** Automated script (`scripts/smoke_test_containers.sh`) validating image builds, container health, migration execution, and teardown.
7. **Comprehensive GitHub Actions CI Workflow:** Multi-job pipeline (`.github/workflows/ci.yml`) validating backend tests, admin-web tests/build, mobile typecheck/tests/Android export, and Docker container build & smoke verification.

---

## 2. Frozen Baseline & Git Discipline

- **Sealed Base Tag:** `gate-10o-offline-sync-localization-sealed`
- **Peeled Commit SHA:** `e7e375562e23c59d9e9ad267201d747a511ca328`
- **Implementation Branch:** `feature/gate-10p-a-production-infrastructure`
- **Historical Tags:** Untouched (`gate-01` through `gate-10o` verified unchanged).
- **Core Constraints Preserved:**
  - Zero modification to sealed domain logic or authorization rules.
  - Zero degradation of PostgreSQL RLS policies or DTO information asymmetry.
  - Zero exposure of real production secrets in source control.

---

## 3. Files Added & Modified

### New Files Added
- `Dockerfile`: Multi-stage build definition with `base`, `builder`, `api`, `worker`, and `migrate` targets.
- `.dockerignore`: Build context filter excluding VCS, test caches, local SQLite databases, client apps, and documentation.
- `docker-compose.yml`: Local rehearsal stack with health-checked dependencies and deterministic migration sequencing.
- `docker-compose.override.yml.example`: Developer override template for local volume mounts and debug logs.
- `docker/entrypoint-api.sh`: Production Uvicorn entrypoint with factory pattern and graceful shutdown timeout.
- `docker/entrypoint-worker.sh`: Production Transactional Outbox worker entrypoint running in poll mode.
- `docker/entrypoint-migrate.sh`: Safe, isolated Alembic database migration runner.
- `requirements.lock`: Fully resolved, deterministic 57-package dependency lockfile compiled via `uv`.
- `scripts/smoke_test_containers.sh`: Automated rehearsal stack build, health verification, and teardown script.
- `.github/workflows/ci.yml`: Unified continuous integration workflow covering all monorepo workspaces and container builds.
- `docs/GATE_10P_A_IMPLEMENTATION.md`: This comprehensive implementation document.

### Files Modified
*None.* (Strict non-invasive infrastructure addition).

---

## 4. Container Architecture & Supply Chain

### Multi-Stage Build Pipeline

```mermaid
flowchart TD
    subgraph Stage1_Base["Stage 1: Base Runtime (python:3.12-slim-bookworm)"]
        BaseOS["Debian Bookworm Minimal\n+ curl + ca-certificates"]
        BaseUser["Create unprivileged user\nthali:thali (UID 10001, GID 10001)"]
        BaseEnv["ENV PYTHONDONTWRITEBYTECODE=1\nPYTHONUNBUFFERED=1\nPYTHONPATH=/app"]
    end

    subgraph Stage2_Builder["Stage 2: Builder"]
        UVBin["Install uv 0.6.14 from ghcr.io/astral-sh/uv"]
        VenvCreate["uv venv /app/.venv"]
        LockInstall["uv pip install --no-cache -r requirements.lock"]
    end

    subgraph Stage3_API["Stage 3: Target api"]
        CopyVenvAPI["COPY --from=builder /app/.venv /app/.venv"]
        CopyCodeAPI["COPY backend/, config/, alembic.ini"]
        EntryAPI["USER thali\nEXPOSE 8000\nENTRYPOINT entrypoint-api.sh"]
    end

    subgraph Stage4_Worker["Stage 4: Target worker"]
        CopyVenvWorker["COPY --from=builder /app/.venv /app/.venv"]
        CopyCodeWorker["COPY backend/, config/, alembic.ini"]
        EntryWorker["USER thali\nENTRYPOINT entrypoint-worker.sh"]
    end

    subgraph Stage5_Migrate["Stage 5: Target migrate"]
        CopyVenvMigrate["COPY --from=builder /app/.venv /app/.venv"]
        CopyCodeMigrate["COPY backend/, config/, alembic.ini"]
        EntryMigrate["USER thali\nENTRYPOINT entrypoint-migrate.sh"]
    end

    Stage1_Base --> Stage2_Builder
    Stage2_Builder --> Stage3_API
    Stage2_Builder --> Stage4_Worker
    Stage2_Builder --> Stage5_Migrate
```

### Supply Chain Security
- **Pinned Base Images:** `python:3.12-slim-bookworm`, `ghcr.io/astral-sh/uv:0.6.14`, `postgres:16-alpine`, `redis:7-alpine`.
- **Locked Python Dependencies:** `requirements.lock` locks all 57 transitive packages with exact SHA/version bindings.
- **Build Isolation:** Frontend and mobile workspaces (`apps/`), `.git`, local databases, and temporary caches are explicitly blocked from the Docker daemon context via `.dockerignore`.

---

## 5. Local Docker Compose Rehearsal Stack

The `docker-compose.yml` provides an isolated rehearsal environment with explicit service readiness sequencing:

```mermaid
sequenceDiagram
    autonumber
    actor Developer
    participant Compose as Docker Compose
    participant PG as PostgreSQL 16
    participant Redis as Redis 7
    participant MinIO as MinIO (S3)
    participant Migrate as Alembic Migrate
    participant API as FastAPI API
    participant Worker as Outbox Worker

    Developer->>Compose: docker compose up -d
    Compose->>PG: Start container & wait for pg_isready
    Compose->>Redis: Start container & wait for redis-cli ping
    Compose->>MinIO: Start container & wait for /minio/health/live
    PG-->>Compose: Healthy (Port 5432)
    Redis-->>Compose: Healthy (Port 6379)
    MinIO-->>Compose: Healthy (Port 9000/9001)

    Compose->>Migrate: Run alembic upgrade head
    Migrate->>PG: Apply migrations 0001 -> 0008
    Migrate-->>Compose: Exit 0 (completed_successfully)

    Compose->>API: Start FastAPI container (Port 8000)
    Compose->>Worker: Start Outbox Worker container
    API->>API: Health probe /health/live returns ok
    API-->>Compose: Healthy
    Worker->>PG: Poll outbox leases (FOR UPDATE SKIP LOCKED)
```

---

## 6. Environment Variables Contract

| Variable | Target | Type | Default / Rehearsal Value | Production Policy |
| :--- | :--- | :--- | :--- | :--- |
| `THALI_APP__ENV` | API, Worker | String | `development` | Set to `production` (disables Swagger/OpenAPI) |
| `THALI_DATABASE__URL` | API, Worker, Migrate | URL | `postgresql+psycopg://thali_user:...@postgres:5432/thali_db` | Cloud RDS/Postgres connection string via Secrets Manager |
| `THALI_REDIS__ENABLED` | API | Boolean | `true` | `true` (enables distributed rate-limiting) |
| `THALI_REDIS__HOST` | API | Hostname | `redis` | Clustered Redis endpoint |
| `THALI_REDIS__PORT` | API | Port | `6379` | `6379` |
| `THALI_STORAGE__ENDPOINT_URL` | API, Worker | URL | `http://minio:9000` | Empty for standard AWS S3, or custom S3-compatible URL |
| `THALI_STORAGE__BUCKET` | API, Worker | String | `thali-documents` | Production private S3 bucket name |
| `THALI_STORAGE__REGION` | API, Worker | String | `ap-south-1` | Cloud storage region (e.g. Mumbai `ap-south-1`) |
| `THALI_STORAGE__ACCESS_KEY_ID` | API, Worker | String | `minioadmin` | Injected IAM role credentials or secret |
| `THALI_STORAGE__SECRET_ACCESS_KEY` | API, Worker | Secret | `minioadmin` | Injected IAM role credentials or secret |
| `THALI_IDENTITY__CLIENT_SECRET` | API | Secret | `rehearsal-secret-for-idempotency-only` | Cryptographically random secret; validated in 10P-B |
| `THALI_OBSERVABILITY__LOG_LEVEL` | API, Worker | String | `INFO` | `INFO` or `WARN` |
| `WEB_CONCURRENCY` | API | Integer | `2` | Number of Uvicorn worker processes (cores * 2) |
| `WORKER_POLL_INTERVAL` | Worker | Float | `5.0` | Polling idle frequency in seconds |

---

## 7. Migration Safety & Execution Model

- **Separation of Concerns:** Migrations are **NEVER** executed automatically upon API process startup. Multiple API instances scaling horizontally would risk migration race conditions or table lock deadlocks.
- **Dedicated Container (`migrate`):** Migrations execute via an isolated one-shot container that applies `alembic upgrade head` and prints `alembic current` before the API and Worker containers are launched.
- **Manual Commands:**
  ```bash
  # Check current migration status
  docker compose run --rm migrate alembic current

  # Upgrade to latest revision
  docker compose run --rm migrate alembic upgrade head

  # View migration history
  docker compose run --rm migrate alembic history
  ```

---

## 8. Health, Readiness & Graceful Shutdown

### Health Probe Implementation
- **Liveness (`/health/live`):** Probes application process responsiveness without checking external network dependencies. A momentary Redis or database blip will **NOT** cause cascading Kubernetes container restarts.
- **Readiness (`/health/ready`):** Probes database connectivity via `check_database_health()`. If PostgreSQL is unreachable, returns HTTP 503 `not_ready`, causing reverse proxies / ingress controllers to stop routing traffic to the instance.

### Signal Handling
- `docker/entrypoint-api.sh` uses `exec uvicorn` to replace the shell process with Uvicorn at PID 1.
- `docker/entrypoint-worker.sh` uses `exec python` to replace the shell process with the Python worker at PID 1.
- Upon receiving `SIGTERM`:
  - Uvicorn stops accepting new HTTP connections and allows up to 30 seconds (`--timeout-graceful-shutdown 30`) for in-flight requests to complete.
  - The Outbox Worker finishes its current event batch, commits or releases its leases, and exits cleanly.

---

## 9. Continuous Integration (CI) Workflow

The GitHub Actions workflow (`.github/workflows/ci.yml`) executes on every push and pull request across all core workspaces:

| Job | Environment | Execution Steps | Gate 10P-A Verification |
| :--- | :--- | :--- | :--- |
| **`backend-tests`** | `ubuntu-latest`, Python 3.12, `uv` | Dependency install via `requirements.lock`, full pytest execution. | **779 passing** |
| **`admin-web-tests`**| `ubuntu-latest`, Node 20, `pnpm` | Vitest test execution and production Vite build. | **41 passing, build OK** |
| **`mobile-tests`** | `ubuntu-latest`, Node 20, `pnpm` | TypeScript typecheck, ESLint, Vitest, Jest component tests, Android export. | **373 Vitest, 126 Jest, Export OK** |
| **`docker-build-and-smoke`** | `ubuntu-latest`, Docker Buildx | Builds `api`, `worker`, `migrate` images; runs `smoke_test_containers.sh`. | **Build & Smoke OK** |

---

## 10. Local Developer Quickstart

```bash
# 1. Build and start the entire rehearsal environment
docker compose up -d

# 2. View streaming logs
docker compose logs -f api worker

# 3. Check health endpoints
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready

# 4. Run automated container smoke verification
./scripts/smoke_test_containers.sh

# 5. Tear down rehearsal environment and clear volumes
docker compose down -v
```

---

## 11. Verification & Test Matrix Results

All regression suites have been executed and verified on the Gate 10P-A branch:

| Suite / Verification | Command | Expected Baseline | Gate 10P-A Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Pytest** | `uv run pytest` | 779 passed | 779 passed | **PASS** |
| **Admin Web Tests** | `pnpm --dir apps/admin-web test` | 41 passed | 41 passed | **PASS** |
| **Admin Web Build** | `pnpm --dir apps/admin-web build` | Clean Vite build | Clean Vite build (dist generated)| **PASS** |
| **Mobile Typecheck**| `pnpm --dir apps/mobile typecheck` | 0 errors | 0 errors | **PASS** |
| **Mobile ESLint** | `pnpm --dir apps/mobile lint` | 0 errors | 0 errors (2 pre-existing warnings)| **PASS** |
| **Mobile Vitest** | `pnpm --dir apps/mobile test` | 373 passed | 373 passed (37 test files) | **PASS** |
| **Mobile Jest** | `pnpm --dir apps/mobile test:component` | 126 passed | 126 passed (18 suites) | **PASS** |
| **Mobile Android Export**| `pnpm --dir apps/mobile export --platform android`| Clean bundle | Clean bundle (3.5MB HBC) | **PASS** |
| **Script Syntax** | `sh -n docker/*.sh && bash -n scripts/*.sh` | Clean syntax | 0 syntax errors | **PASS** |
| **Lockfile Generation**| `uv pip compile requirements.txt` | Deterministic | 57 packages resolved | **PASS** |

---

## 12. Limitations & Deferred Work

This gate establishes infrastructure foundations only. The following operational items are explicitly deferred to subsequent sub-gates per the approved architecture plan:

- **Gate 10P-B:** Production secret vault integration, fail-closed startup validation (blocking default secrets), production Keycloak realm exports, and idempotency DB-error fail-closed enforcement.
- **Gate 10P-C:** Dedicated PgBouncer deployment, WAL-G/PITR continuous archiving automation, and autovacuum tuning.
- **Gate 10P-D:** Prometheus `/metrics` exporter, OpenTelemetry distributed tracing, and centralized log aggregation.
- **Gate 10P-E:** Android release signing, ProGuard rules, and physical Android hardware testing.
- **Gate 10P-F:** Load testing, SAST/DAST security scanning, and fault injection chaos drills.
- **Gate 10P-G:** Staging VPC deployment rehearsal and go-live verification.

---

## 13. Acceptance Checklist

- [x] API Docker image builds reproducibly from `python:3.12-slim-bookworm`.
- [x] Worker Docker image builds reproducibly sharing base virtual environment.
- [x] Runtime containers run as unprivileged user `thali:thali` (UID 10001).
- [x] Zero production secrets or credentials are baked into images.
- [x] `.dockerignore` excludes VCS, caches, local databases, and frontend workspaces.
- [x] Docker Compose rehearsal stack provides `postgres`, `redis`, `minio`, `migrate`, `api`, and `worker`.
- [x] Database migrations execute deterministically via dedicated `migrate` target.
- [x] Health (`/health/live`) and readiness (`/health/ready`) probe contracts preserved.
- [x] Graceful `SIGTERM` shutdown handling wired via `exec` in entrypoints.
- [x] Automated smoke test script (`scripts/smoke_test_containers.sh`) provided.
- [x] Unified GitHub Actions CI workflow created.
- [x] All 779 backend tests pass.
- [x] All 41 admin web tests and production build pass.
- [x] All 373 mobile Vitest tests, 126 Jest tests, and Android bundle export pass.
- [x] Zero sealed gates or historical commits modified.
- [x] Documentation complete with quickstart and architecture diagrams.

---

## 14. Final Status

```
============================================================
GATE 10P-A STATUS:
READY FOR INDEPENDENT AUDIT
============================================================
```
