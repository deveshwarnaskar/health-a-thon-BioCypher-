# THALI × P.L.A.T.E. — Clinical Telemetry & Longitudinal Glycemic Intelligence

> **Health-a-thon 2026 · Diabetes Care Track · Production Clinician & Patient Ecosystem**  
> **Architecture:** Unified Mobile Client (React Native / Expo) + Shared FastAPI Platform + WhatsApp Telemetry  
> **Security & Identity:** PostgreSQL-backed RS256/HS256 JWT Authentication with Role-Based Access Control  
> **Clinical Classification:** Assistive Decision-Support Telemetry Engine (Strictly Non-Diagnostic)

---

## 1. Executive Summary & System Vision

**THALI** (*Telemetric Health Analytics & Longitudinal Ingestion*) × **P.L.A.T.E.** (*Patient Longitudinal Assessment & Treatment Engine*) is an enterprise-grade clinical telemetry platform designed for outpatient endocrinology and diabetes care departments (OPD).

Contemporary diabetes consultations are challenged by episodic, context-free glucometer prick logs and unreliable, retrospective dietary recall. THALI × P.L.A.T.E. bridges this gap:
1. **Asynchronous Ingestion:** Captures raw, multi-modal patient inputs via **WhatsApp Cloud API** (free-text meal descriptions in colloquial Hinglish, glucometer numbers, food photos) and the **THALI Mobile App**.
2. **Volumetric Intake Normalization:** Employs an Indian food taxonomy (35+ common staples) and standardized household volumetric portioning (**Small / 150 ml**, **Medium / 220 ml**, **Large / 350 ml** *katoris*).
3. **Clinical Information Asymmetry:** Patient and caregiver interfaces speak strictly in colloquial volumetric units. Carbohydrate gram weights, Glycemic Index (GI) ratings, and Glycemic Volatility metrics are strictly doctor-only context.
4. **Longitudinal Glycemic Metrics Engine:** Aggregates blood glucose observations alongside confirmed meal chronobiology into Time-in-Range (TIR), Carb Volatility Index (CVI), Pearson correlation ($r$), and meal-slot distributions (Post-Breakfast, Post-Lunch, Post-Dinner, Weekday vs. Weekend).
5. **Unified Clinician Ecosystem:** Exposes live telemetry via the **Universal Mobile Application** (Doctor Review Queue, patient cohorts, and AI draft approvals), the **Clinician Web Dashboard**, and automated **2-Page Lab-Grade A4 PDF Reports**.

---

## 2. System Architecture

```
                            +-------------------------------------------------------------+
                            |                     PATIENT / CAREGIVER                     |
                            |   WhatsApp: Free-text, Hinglish, Prick Numbers, Photos      |
                            |   Mobile App: React Native / Expo (Offline-Sync SQLite)     |
                            +------------------------------+------------------------------+
                                                           |
                                  HTTPS (Meta Cloud API / Webhook & REST API)
                                                           |
                                                           v
+-------------------------------------------------------------------------------------------------------+
|                                    BACKEND REST API & INTAKE ENGINE                                   |
|                                                                                                       |
|  +---------------------------------+  Custom RS256 JWT  +------------------------------------------+  |
|  |       Auth & Security API       | -----------------> | PostgreSQL RLS Engine                    |  |
|  |  - /api/v2/auth/login, refresh  |  (Bcrypt Hash,     | - multi-tenant schema isolation          |  |
|  |  - /api/v2/auth/logout, register|   RSA-2048 Tokens) | - users, organizations, facilities       |  |
|  +----------------+----------------+                    +--------------------+---------------------+  |
|                   |                                                          |                        |
|                   v                                                          |                        |
|  +---------------------------------+                                         |                        |
|  |     Hinglish Dietary Parser     |                                         |                        |
|  |  - 35-Staple Indian Taxonomy    |                                         |                        |
|  |  - Katori Volumetric Portioning |                                         |                        |
|  |  - Ambiguity Guard & Nudges     |                                         |                        |
|  +----------------+----------------+                                         |                        |
|                   |                                                          |                        |
|                   v                                                          |                        |
|  +---------------------------------+  Interactive Confirm   +----------------+---------------------+  |
|  |      WhatsApp Confirm Loop      | <--------------------> | Durable Telemetry Store              |  |
|  |  - Propose katori portion       |     (YES / corr)       | - Glucose & Meal Observations        |  |
|  |  - Asymmetric reply shielding   |                        | - Caregiver Relationships            |  |
|  +----------------+----------------+                        | - AI Review Artifacts                |  |
|                   |                                         +----------------+---------------------+  |
|                   | Clean Verified Telemetry                                 |                        |
|                   v                                                          v                        |
|  +---------------------------------+                        +----------------+---------------------+  |
|  |     Glycemic Metrics Engine     |                        |      Transactional Outbox            |  |
|  |  - TIR (70-180 mg/dL: in/hi/lo) |                        |  - Reliable event dispatch           |  |
|  |  - CVI & Pearson Correlation    |                        |  - Worker background processor       |  |
|  |  - Meal slots: PB, PL, PD       |                        +--------------------------------------+  |
|  |  - Weekday vs. Weekend surges   |                                                                  |
|  +----------------+----------------+                                                                  |
+-------------------|-----------------------------------------------------------------------------------+
                    |
                    +-----------------------------------+
                    |                                   |
                    v                                   v
+---------------------------------------+   +-----------------------------------------------+
|         REPORT RENDERING ENGINE       |   |             CLINICIAN INTERFACES              |
|                                       |   |                                               |
| - Matplotlib Agg Headless Charts      |   | - Clinician Dashboard: Responsive HTML5/JS    |
| - ReportLab 2-Page Publication PDF    |   | - Mobile: Patient / Clinician Expo App        |
| - Object Storage (MinIO / S3)         |   |                                               |
+---------------------------------------+   +-----------------------------------------------+
```

---

## 3. Directory Layout

```
├── apps/
│   └── mobile/                      # Expo / React Native Cross-Platform Mobile Client
│       ├── app/                     # Expo file-based router & screens
│       ├── src/                     # Offline sync (SQLite), state management, direct auth
│       └── test/                    # Vitest & Jest component tests (391 tests)
│
├── backend/
│   ├── domain/                      # Pure Python domain entities, value objects & services
│   │   ├── entities/                # Patient, GlucoseObservation, MealObservation, etc.
│   │   ├── services/                # GlycemicMetricsService (TIR, CVI, Pearson r)
│   │   └── value_objects/           # UHID, PhoneNumber, GlucoseValue, ReadingTag
│   │
│   ├── application/                 # Orchestration, use cases, and ops workflows
│   │   ├── commands/                # CQRS command handlers
│   │   ├── queries/                 # Read queries & report builders
│   │   └── ops/                     # WhatsApp confirm loop, intake, and handlers
│   │
│   ├── infrastructure/              # External technology adapters & database
│   │   ├── auth/                    # TokenService (RS256/HS256) & PasswordService (bcrypt)
│   │   ├── parsing/                 # HinglishParser & 35-Staple NutritionTaxonomy
│   │   ├── persistence/             # SQLAlchemy models, repositories, and Alembic migrations
│   │   ├── reporting/               # Matplotlib charts & ReportLab 2-page PDF renderer
│   │   └── storage/                 # S3 / MinIO object storage provider
│   │
│   └── interfaces/                  # Entry points (HTTP API & Static UI)
│       └── http/
│           ├── app.py               # FastAPI application definition & middleware
│           ├── dependencies.py      # Dependency injection & token verification
│           ├── static/              # Clinician Web Dashboard (HTML/CSS/JS)
│           └── v2/                  # Versioned API routes (auth, patients, meals, etc.)
│
├── config/                          # Typed configuration & dev keys
│   ├── dev_keys/                    # RSA-2048 keypair for local development
│   └── settings.py                  # Pydantic v2 settings schema
│
├── docker/                          # Container definitions (API, Worker, Migrate)
├── docs/                            # Architecture reports, runbooks, and specifications
├── scripts/                         # CLI automation (seeding, key generation, smoke tests)
└── tests/                           # Pytest test suite (894 tests)
```

---

## 4. Authentication & Security Architecture

Keycloak has been entirely removed and replaced with a lean, custom **PostgreSQL-backed RS256/HS256 JWT Authentication Engine**:

- **Password Hashing:** Passwords hashed with salted `bcrypt` (12 rounds).
- **Dual-Mode Tokens:**
  - **Production:** Strictly RS256 with an RSA-2048 private key (`THALI_AUTH__PRIVATE_KEY_PEM`) and public key (`THALI_AUTH__PUBLIC_KEY_PEM`).
  - **Development:** Pre-generated RSA keys in `config/dev_keys/` with automated fallback to HS256 in test harnesses.
- **Token Endpoints:**
  - `POST /api/v2/auth/login`: Accepts `{"email", "password"}` and issues an `access_token` (60m) and `refresh_token` (7d).
  - `POST /api/v2/auth/refresh`: Validates refresh token and issues a new access token.
  - `POST /api/v2/auth/logout`: Revokes active refresh token.
  - `POST /api/v2/auth/register`: Admin-only endpoint for provisioning workforce and clinician accounts.
- **Tenant Isolation:**
  - PostgreSQL Row-Level Security (`RLS`) enforced on all relational queries via `SqlAlchemyUnitOfWork`.
  - The JWT claims `sub`, `tenant_id`, and `role` drive the database session configuration (`set_config('app.current_tenant_id', ...)`).

---

## 5. Clinical Telemetry & Glycemic Engine

### Indian Nutrition Taxonomy & Hinglish Parser
- **35 Common Indian Staples:** Calibrated against national nutritional databases (roti, dal, chawal, paratha, khichdi, paneer, poha, idli, dosa, sabzi, etc.).
- **Household Volumetric Units:** Standardized to Indian household bowls:
  - **Small:** 150 ml
  - **Medium:** 220 ml
  - **Large:** 350 ml
- **Dialect Handling:** Normalizes phonetic Hinglish, typo variations, and colloquial expressions (e.g., *"ek katori dal aur do roti khaya"*).

### Strict Information Asymmetry Guarantee
- **Patient & WhatsApp View:** Strictly volumetric portion estimates ("Small (150 ml)", "Medium (220 ml)"). No carbohydrate weights (grams), glycemic index categories, or raw gram estimates are ever exposed to patients.
- **Doctor View:** Full clinical context including carb weights, glycemic index (Low / Med / High), Carb Volatility Index (CVI), and meal-slot correlations.

### Glycemic Metrics Engine
- **Time-in-Range (TIR):** Strict consensus boundaries (70–180 mg/dL target; < 70 hypoglycemia; > 180 hyperglycemia).
- **Meal-Slot Segmentation:** Segmented into Post-Breakfast (PB), Post-Lunch (PL), and Post-Dinner (PD).
- **Chronobiology Analysis:** Tracks weekday vs. weekend glycemic shifts and postprandial surges.
- **Statistical Modeling:** Computes Pearson correlation coefficient ($r$) between daily dietary intake and postprandial spikes.

---

## 6. Quickstart & Local Development

### Prerequisites
- Python 3.12+ (or 3.14) with `uv` or standard `venv`
- Node.js 20+ and `pnpm`
- Docker & Docker Compose

### 1. Environment & Dev Keys
Generate the local RSA-2048 keypair (already included in `config/dev_keys/`):
```bash
python -m scripts.generate_dev_keys
```

Copy the environment template:
```bash
cp .env.example .env
```

### 2. Start Supporting Services
```bash
docker compose up -d postgres redis minio
```

### 3. Run Migrations & Seed Database
```bash
# Run Alembic migrations
./.venv/bin/alembic upgrade head

# Seed dev tenant, workforce accounts, and Sita Sharma
./.venv/bin/python -m scripts.seed_dev_stack
```

#### Pre-Seeded Development Credentials:
| Email | Password | Role | Facility |
| :--- | :--- | :--- | :--- |
| `admin@thali.dev` | `thali-dev-password-123` | System Administrator | Apex Diabetes Center |
| `doctor@thali.dev` | `thali-dev-password-123` | Treating Endocrinologist | Apex Diabetes Center |
| `nurse@thali.dev` | `thali-dev-password-123` | Care Coordinator | Apex Diabetes Center |
| `patient@thali.dev` | `thali-dev-password-123` | Patient (Sita Sharma) | Apex Diabetes Center |

### 4. Launch Application Services

**Backend API:**
```bash
./.venv/bin/uvicorn backend.interfaces.http.app:create_app --factory --reload --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Clinician Dashboard: `http://localhost:8000/`

**Mobile App (Expo):**
```bash
pnpm --dir apps/mobile install
pnpm --dir apps/mobile start
```

---

## 7. Test Suite & Verification

The platform maintains full test coverage across all architectural boundaries:

| Test Suite | Framework | Count | Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Backend API** | Pytest | 472 | PASS | HTTP boundary, custom JWT auth, RLS, contracts, ops |
| **Backend Unit** | Pytest | 259 | PASS | Pure domain logic, entities, glycemic metrics, taxonomy |
| **Backend Security** | Pytest | 90 | PASS | Multi-tenant isolation, tamper protection, RS256 boundary |
| **Backend Integration** | Pytest | 50 | PASS | PostgreSQL RLS transactions, Alembic, chaos recovery |
| **Observability** | Pytest | 23 | PASS | Structured logs, metrics, audit trail |
| **Mobile App** | Vitest / Jest | 391 | PASS | Direct auth, offline-sync SQLite, UI components |
| **Total** | | **1,285** | **100% PASS** | End-to-end verified with zero failures |

Run all tests locally:
```bash
# Backend pytest suite (894+ tests)
./.venv/bin/pytest tests/

# Mobile test suite (391 tests)
pnpm --dir apps/mobile test
```

---

## 8. License

Licensed under the BSD-3-Clause License. See [LICENSE](LICENSE) for details.