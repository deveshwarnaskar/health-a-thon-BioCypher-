# THALI × P.L.A.T.E. — Deployment & Operations Guide

This guide details the deployment procedure for the **THALI × P.L.A.T.E.** platform, covering local container rehearsal, staging, and production environments.

---

## 1. Architecture & Service Topology

The THALI × P.L.A.T.E. stack comprises the following containerized services orchestrated via Docker Compose or Kubernetes:

| Service | Container Image Target | Port | Purpose |
| :--- | :--- | :--- | :--- |
| **`postgres`** | `postgres:16-alpine` | `5432` | Primary relational database with Row-Level Security (`RLS`) |
| **`redis`** | `redis:7-alpine` | `6379` | Ephemeral caching & rate limiting |
| **`minio`** | `quay.io/minio/minio:RELEASE.2024-01-18T22-51-28Z` | `9000`, `9001` | S3-compatible document storage (PDF clinical reports & assets) |
| **`migrate`** | `thali-migrate` (`Dockerfile:migrate`) | None | One-off Alembic database migration runner to `head` |
| **`api`** | `thali-api` (`Dockerfile:api`) | `8000` | FastAPI asynchronous HTTP application & static clinician UI |
| **`worker`** | `thali-worker` (`Dockerfile:worker`) | None | Asynchronous outbox processor & background worker daemon |

---

## 2. Authentication Configuration (Custom RS256)

THALI × P.L.A.T.E. utilizes an integrated, PostgreSQL-backed **RS256 JWT Authentication Engine**, eliminating the operational overhead of external identity providers (e.g. Keycloak).

### Generating Production RSA Keys
In production, generate a cryptographically strong RSA-2048 keypair:

```bash
# Generate private key
openssl genrsa -out private_key.pem 2048

# Extract public key
openssl rsa -in private_key.pem -pubout -out public_key.pem
```

Inject these keys into the environment as single-line strings with escaped newlines (`\n`) or via Docker secrets / Kubernetes secrets:
```bash
export THALI_AUTH__PRIVATE_KEY_PEM="$(cat private_key.pem)"
export THALI_AUTH__PUBLIC_KEY_PEM="$(cat public_key.pem)"
```

### Local Development Keys
For local development, pre-generated keys are stored in `config/dev_keys/` and can be re-generated at any time using:
```bash
python -m scripts.generate_dev_keys
```

---

## 3. Environment Variables Reference

| Variable | Description | Default (Dev) | Production Requirement |
| :--- | :--- | :--- | :--- |
| `THALI_APP__ENV` | Application environment (`development`, `staging`, `production`) | `development` | Must be `production` |
| `THALI_DATABASE__URL` | SQLAlchemy PostgreSQL connection string | `postgresql://thali:thali_dev_pass@postgres:5432/thali` | Required (TLS recommended) |
| `THALI_REDIS__ENABLED` | Enable Redis for rate limiting | `false` | `true` |
| `THALI_REDIS__HOST` | Redis host | `redis` | Redis cluster hostname |
| `THALI_STORAGE__ENDPOINT_URL` | S3 / MinIO endpoint | `http://minio:9000` | S3 endpoint URL |
| `THALI_STORAGE__BUCKET` | S3 bucket name | `thali-documents` | Configured S3 bucket |
| `THALI_STORAGE__ACCESS_KEY_ID` | Storage access key | `minioadmin` | Non-default secret key |
| `THALI_STORAGE__SECRET_ACCESS_KEY` | Storage secret key | `minioadmin` | Non-default secret key |
| `THALI_AUTH__PRIVATE_KEY_PEM` | RSA-2048 private key for signing JWTs | Loaded from `config/dev_keys/` | Required RSA-2048 PEM |
| `THALI_AUTH__PUBLIC_KEY_PEM` | RSA-2048 public key for verifying JWTs | Loaded from `config/dev_keys/` | Required RSA-2048 PEM |
| `THALI_AUTH__ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifespan | `60` | `15` to `60` minutes |
| `THALI_AUTH__REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifespan | `7` | `7` to `30` days |
| `THALI_WHATSAPP__VERIFY_TOKEN` | Meta Webhook verify token | `thali-dev-verify-token` | High-entropy secret |
| `THALI_WHATSAPP__APP_SECRET` | Meta App Secret for HMAC validation | `dev-webhook-secret` | Meta App Secret |

---

## 4. Local Deployment via Docker Compose

### 1. Build and Start Core Infrastructure
```bash
docker compose up -d postgres redis minio
```

Wait for health checks to pass:
```bash
docker compose ps
```

### 2. Run Database Migrations
```bash
docker compose run --rm migrate
```

### 3. Seed Development Database
Populate the database with the default tenant (`thali-dev`), facility (`Apex Diabetes Center`), workforce accounts, and the baseline patient Sita Sharma:
```bash
docker compose run --rm api python -m scripts.seed_dev_stack
```

### 4. Start API and Background Worker
```bash
docker compose up -d api worker
```

### 5. Verify Health Endpoints
- **Liveness probe:**
  ```bash
  curl -s http://localhost:8000/health/live
  # Response: {"status": "ok", "app": "THALI-PLATE", "version": "0.1.0"}
  ```
- **Readiness probe:**
  ```bash
  curl -s http://localhost:8000/health/ready
  # Response: {"status": "ok", "database": "connected", "storage": "connected"}
  ```

---

## 5. Automated Container Smoke Test

The repository includes a self-contained rehearsal verification script that performs an end-to-end sanity check on Docker Compose:

```bash
./scripts/smoke_test_containers.sh
```

The script executes 6 verification phases:
1. Validates Compose configuration syntax.
2. Builds all container targets (`api`, `worker`, `migrate`).
3. Starts infrastructure dependencies (`postgres`, `redis`, `minio`).
4. Executes Alembic migrations to head.
5. Boots `api` and `worker`, polling `/health/live` and `/health/ready`.
6. Performs graceful teardown and volume cleanup.

---

## 6. Frontend Deployment

### Mobile Application (`apps/mobile`)
Built using Expo Application Services (EAS) or exported statically:
```bash
# Typecheck and test
pnpm --dir apps/mobile typecheck
pnpm --dir apps/mobile test

# Export bundle
pnpm --dir apps/mobile export --platform android
```

---

## 7. Production Security Checklist

Prior to promoting to production:
1. Ensure `THALI_APP__ENV=production` is set.
2. Confirm `THALI_AUTH__PRIVATE_KEY_PEM` and `THALI_AUTH__PUBLIC_KEY_PEM` are set to production-grade RSA-2048 keys.
3. Verify that `THALI_DATABASE__URL` connects with SSL enabled (`sslmode=require`).
4. Replace all default passwords for PostgreSQL, Redis, MinIO/S3, and WhatsApp webhooks.
5. Set `THALI_SECURITY__ALLOWED_ORIGINS` to explicit HTTPS domain origins (no wildcards `*` permitted in production).
