# GATE 02A — REPOSITORY ARCHITECTURE & MIGRATION MAP
## THALI × P.L.A.T.E. Production Program

**Gate ID**: `GATE-02A`  
**Classification**: Planning & Scaffolding Blueprint Only (Read-Only Audit & Design)  
**Status**: **READY FOR SCAFFOLDING**  
**Execution Date**: 2026-09-13  
**Target Repository**: `/Users/subhamdas/Documents/health-a-thon-BioCypher--master`  
**Author**: Antigravity Architecture Reconnaissance & Migration Engine  

---

## Executive Summary

This document establishes the authoritative repository restructuring plan and migration blueprint for transitioning the **Aahaar (Health-a-thon 2026)** prototype into the enterprise **THALI × P.L.A.T.E.** multi-tenant production system.

In strict compliance with the **GATE 02A** mandate:
- **No source code has been modified, moved, renamed, or refactored.**
- **No database migrations have been executed.**
- **No dependencies have been installed.**
- **No authentication or RBAC logic has been implemented.**
- **All 57 existing baseline tests remain intact, passing 100% in 2.69s.**
- **A critical Git safety issue was detected and documented (the directory lacks a `.git` tracking tree and requires baseline initialization prior to physical code manipulation).**

The blueprint establishes a clean transition from the legacy monolithic script layout to a modular **Clean Architecture / Hexagonal** pattern (`domain`, `application`, `infrastructure`, `interfaces`, `compatibility`) while maintaining a non-breaking compatibility bridge that ensures continuous operation of the 57 baseline tests.

---

## 1. Current Exact Repository Tree

The following filesystem tree represents the physical state of the repository as verified by direct directory walks. No speculative files or inferred structures are included.

```
/Users/subhamdas/Documents/health-a-thon-BioCypher--master/
│
├── .gitignore                                [382 B, 38 lines]
├── LICENSE                                   [1,513 B, 29 lines]
├── README.md                                 [40,012 B, 610 lines]
├── pytest.ini                                [42 B, 4 lines]
├── requirements.txt                          [121 B, 8 lines]
│
├── GATE_00_EXISTING_SYSTEM_AUDIT.md          [85,376 B, 1,024 lines]
├── GATE_00_VERIFICATION.md                   [13,195 B, 212 lines]
├── GATE_01_ARCHITECTURE_RECONCILIATION.md    [66,330 B, 869 lines]
├── GATE_01_1_ARCHITECTURE_CORRECTIONS.md     [26,203 B, 396 lines]
│
├── aahaar.db                                 [69,632 B, SQLite database - persistent storage]
├── aahaar-demo.db                            [4,096 B, SQLite database - demo instance]
├── aahaar-demo.db-shm                        [32,768 B, SQLite shared memory index]
├── aahaar-demo.db-wal                        [156,592 B, SQLite write-ahead log]
│
├── app/                                      [Application source root]
│   ├── __init__.py                           [6 lines] Package root
│   ├── config.py                             [81 lines, 4,010 B] Central prototype settings dataclass
│   │
│   ├── core/                                 [Business logic, intake, NLP, and SQLite persistence]
│   │   ├── __init__.py                       [0 lines] Core package init
│   │   ├── ai.py                             [367 lines, 15,375 B] Conversational AI, typo map, Gemini/Groq caller
│   │   ├── ai_worker.py                      [335 lines, 16,337 B] Background intake worker polling stored rows
│   │   ├── datamodel.py                      [452 lines, 21,335 B] Monolithic SQLite Store, DDL, queries, raw SQL
│   │   ├── escalation.py                     [62 lines, 2,176 B] Missed logging escalation engine (9 PM nudge)
│   │   ├── intake_ai.py                      [305 lines, 14,714 B] AI intake notifier, meal extraction, clarification
│   │   ├── metrics.py                        [254 lines, 10,879 B] TIR, PPBG, fasting, meal-slot aggregation
│   │   ├── nutrition.py                      [236 lines, 10,037 B] Dish catalog, katori volume calculation, carb/GI DB
│   │   ├── parse.py                          [305 lines, 11,957 B] Inbound text regex parser, portion/reading extractor
│   │   ├── process.py                        [250 lines, 10,676 B] IngestService, confirm loop, 2-number rule, auto-bind
│   │   ├── report.py                         [197 lines, 7,867 B] Clinical report context builder & text templates
│   │   └── seed.py                           [40 lines, 1,733 B] 14-day demo synthetic clinical data generator
│   │
│   ├── report/                               [Document rendering engine]
│   │   ├── __init__.py                       [0 lines] Report package init
│   │   ├── charts.py                         [160 lines, 6,432 B] Matplotlib chart generator (scatter, TIR bars, slots)
│   │   ├── html_preview.py                   [284 lines, 12,045 B] Browser-rendered HTML report template
│   │   └── pdf.py                            [529 lines, 20,443 B] ReportLab 2-page clinical PDF generator
│   │
│   ├── server/                               [HTTP API & Webhook Layer]
│   │   ├── __init__.py                       [0 lines] Server package init
│   │   ├── main.py                           [622 lines, 28,700 B] FastAPI application, /api/v1 routes, static mount
│   │   └── whatsapp.py                       [490 lines, 21,330 B] Meta Cloud API & Simulator backends
│   │
│   └── static/                               [Legacy Vanilla JS Dashboard - Zero build tooling]
│       ├── app.js                            [645 lines, 25,695 B] Client-side dashboard logic, polling, state
│       ├── index.html                        [223 lines, 9,692 B] Static dashboard HTML structure
│       └── style.css                         [186 lines, 4,028 B] Dashboard stylesheet
│
├── docs/                                     [Documentation]
│   └── WHATSAPP_DEMO.md                      [138 lines, 4,374 B] Meta WhatsApp setup & webhook test runbook
│
├── scripts/                                  [Utility scripts & Seeders]
│   ├── analyze_stored.py                     [80 lines, 3,248 B] CLI offline runner for stored raw messages
│   ├── demo.py                               [195 lines, 8,633 B] End-to-end interactive demo simulator
│   └── seed_real.py                          [41 lines, 1,791 B] Dedicated DB seeder for test runs
│
├── tests/                                    [Verification Test Suite]
│   ├── conftest.py                           [36 lines, 794 B] Pytest fixtures (tmp SQLite store, config, seeded demo)
│   ├── test_linking.py                       [250 lines, 9,848 B] 16 tests: Operator key, phone linking, webhooks
│   └── test_pipeline.py                      [781 lines, 34,772 B] 41 tests: Parsing, confirm loop, TIR, AI worker
│
├── .venv/                                    [Python 3.14 virtual environment - gitignored]
└── .pytest_cache/                            [Pytest execution cache - gitignored]
```

### 1.1 Source Code & Asset Statistics

| Subsystem / Directory | Python Files | Non-Python Files | Total Lines of Code | Primary Role |
| :--- | :---: | :---: | :---: | :--- |
| `app/core/` | 12 | 0 | 2,897 | Core business logic, parsing, SQLite storage, and NLP |
| `app/report/` | 3 | 0 | 973 | ReportLab PDF rendering, HTML preview, Matplotlib charts |
| `app/server/` | 2 | 0 | 1,112 | FastAPI HTTP routing, static mount, Meta webhook receiver |
| `app/static/` | 0 | 3 | 1,054 | Legacy Vanilla JS clinical dashboard (Phase 1 legacy/debug) |
| `app/ (root)` | 2 | 0 | 87 | Application init, Settings dataclass |
| `scripts/` | 3 | 0 | 316 | Automation, offline batch processing, manual demo |
| `tests/` | 3 | 0 | 1,067 | 57 automated verification tests (100% pass) |
| `docs/` | 0 | 1 | 138 | Meta WhatsApp integration runbook |
| **Total Source Assets** | **22** | **4** | **7,644** | Complete baseline codebase |

---

## 2. Proposed Target Repository Tree

The target repository structure adopts a **Clean Architecture / Hexagonal (Ports and Adapters)** architecture. The core application logic is strictly isolated from databases, network protocols, UI frameworks, and external APIs.

```
health-a-thon-BioCypher--master/
│
├── .github/                                  # CI/CD workflows (lint, test, build, audit)
│   └── workflows/
│       ├── test-baseline.yml                 # Continuous execution of the 57 baseline tests
│       └── backend-ci.yml                    # Unit, domain, integration, and security checks
│
├── apps/                                     # User-facing applications (Monorepo boundaries)
│   │
│   ├── mobile/                               # UNIVERSAL MOBILE APPLICATION (Phase 1)
│   │   │                                     # React Native + Expo (Expo Router, Zustand, TanStack Query,
│   │   │                                     # React Hook Form + Zod, Expo SQLite + SQLCipher, Drizzle ORM)
│   │   ├── app/                              # Expo Router file-based route tree
│   │   │   ├── (auth)/                       # Keycloak authentication / login screens
│   │   │   ├── (patient)/                    # THALI Patient experience (Katori visual logging, readings)
│   │   │   ├── (caregiver)/                  # THALI Caregiver experience (dependent monitoring)
│   │   │   └── (clinician)/                  # P.L.A.T.E. Mobile-First (Doctor, Nurse, Coord, Dietitian, Field)
│   │   ├── src/
│   │   │   ├── components/                   # Shared design system & clinical widgets
│   │   │   ├── db/                           # Expo SQLite + SQLCipher + Drizzle ORM schemas
│   │   │   ├── stores/                       # Zustand client state stores
│   │   │   ├── api/                          # TanStack Query hooks & OpenAPI client
│   │   │   └── schemas/                      # Zod validation schemas
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── admin-web/                            # ADMIN WEB CONSOLE (Phase 1)
│   │   │                                     # React / Next.js / Vite SPA for tenant & facility ops
│   │   ├── src/
│   │   │   ├── components/                   # Facility, tenant, and user management UI
│   │   │   ├── pages/                        # Admin console views
│   │   │   └── api/                          # Admin REST client
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── clinical-workstation/                 # P.L.A.T.E. CLINICAL WEB (Phase 2 - DEFERRED)
│   │   └── README.md                         # Placeholder for future large-screen OPD dashboard
│   │
│   └── legacy-dashboard/                     # AAHAAR LEGACY/DEBUG DASHBOARD (Preserved from app/static/)
│       ├── app.js                            # Preserved vanilla JS debug interface
│       ├── index.html                        # Preserved HTML structure
│       └── style.css                         # Preserved CSS styles
│
├── backend/                                  # SHARED FASTAPI BACKEND (Clean Architecture)
│   │
│   ├── domain/                               # PURE DOMAIN LAYER (Zero external dependencies)
│   │   ├── __init__.py
│   │   ├── entities/                         # Aggregate roots and domain entities
│   │   │   ├── __init__.py
│   │   │   ├── user.py                       # User entity (clinicians, patients, caregivers)
│   │   │   ├── organization.py               # Multi-tenant Organization & Facility entities
│   │   │   ├── patient.py                    # PatientProfile entity (clinical baseline, targets)
│   │   │   ├── care_plan.py                  # CarePlan entity & targets
│   │   │   ├── medication_plan.py            # MedicationPlan entity (clinician-authored ONLY)
│   │   │   └── care_team.py                  # CareTeamMembership & CaregiverRelationship
│   │   │
│   │   ├── value_objects/                    # Immutable domain primitives & business validation
│   │   │   ├── __init__.py
│   │   │   ├── glucose.py                    # GlucoseMeasurement (sanity range: 20-600 mg/dL)
│   │   │   ├── meal_portion.py               # MealPortion (Katori S/M/L, ml volumes)
│   │   │   ├── reading_tag.py                # ReadingTag (fasting, pre, postprandial, etc.)
│   │   │   ├── phone_number.py               # E.164 validated phone number
│   │   │   ├── uhid.py                       # Unique Healthcare Identifier
│   │   │   └── time_window.py                # Clinical logging window (7, 14, 21 days)
│   │   │
│   │   ├── events/                           # Append-Only Canonical Domain Events
│   │   │   ├── __init__.py
│   │   │   ├── base.py                       # BaseDomainEvent with event_id, tenant_id, timestamp
│   │   │   ├── glucose_events.py             # ObservationGlucoseLoggedEvent
│   │   │   ├── meal_events.py                # IntakeMealLoggedEvent, MealPortionConfirmedEvent
│   │   │   ├── medication_events.py          # MedicationAdministeredEvent
│   │   │   ├── clinical_events.py            # CareTaskCreatedEvent, CarePlanUpdatedEvent
│   │   │   └── communication_events.py       # InboundMessageReceivedEvent, OutboundMessageSentEvent
│   │   │
│   │   ├── exceptions/                       # Domain-specific business exceptions
│   │   │   ├── __init__.py
│   │   │   ├── clinical_guard.py             # Non-diagnostic guard violations, sanity errors
│   │   │   └── auth_guard.py                 # 2-number rule violations, permission errors
│   │   │
│   │   └── repositories/                     # Abstract Domain Repository Ports (Interfaces)
│   │       ├── __init__.py
│   │       ├── patient_repo.py               # IPatientRepository
│   │       ├── organization_repo.py          # IOrganizationRepository
│   │       ├── care_plan_repo.py             # ICarePlanRepository
│   │       ├── event_store_repo.py           # ICanonicalEventRepository
│   │       └── audit_repo.py                 # IAuditLogRepository
│   │
│   ├── application/                          # APPLICATION USE CASES & ORCHESTRATION
│   │   ├── __init__.py
│   │   ├── commands/                         # State-changing write workflows (CQRS Commands)
│   │   │   ├── __init__.py
│   │   │   ├── ingest_glucose.py             # IngestGlucoseReadingCommand & Handler
│   │   │   ├── log_meal_draft.py             # LogMealDraftCommand & Handler
│   │   │   ├── confirm_meal_portion.py       # ConfirmMealPortionCommand & Handler
│   │   │   ├── log_medication_admin.py       # LogMedicationAdminCommand & Handler
│   │   │   ├── evaluate_escalations.py       # EvaluateEscalationsCommand (9 PM missed logging)
│   │   │   └── link_patient_phone.py         # LinkPatientPhoneCommand & Handler
│   │   │
│   │   ├── queries/                          # Read-only query workflows (CQRS Queries)
│   │   │   ├── __init__.py
│   │   │   ├── get_patient_metrics.py        # ComputeWindowMetricsQuery & Handler
│   │   │   ├── get_clinical_report.py        # BuildClinicalReportContextQuery & Handler
│   │   │   └── get_live_inbound.py           # GetLiveInboundFeedQuery & Handler
│   │   │
│   │   ├── dtos/                             # Asymmetric projection DTOs (Pydantic v2)
│   │   │   ├── __init__.py
│   │   │   ├── patient_facing.py             # Patient-facing DTOs (volumetric katori, NO carbs/GI)
│   │   │   ├── clinician_facing.py           # Clinician-facing DTOs (carbs, GI, TIR, PPBG stats)
│   │   │   └── admin_facing.py               # Admin DTOs (tenants, facilities, audit logs)
│   │   │
│   │   ├── ports/                            # Secondary / Driven Outbound Ports (Interfaces)
│   │   │   ├── __init__.py
│   │   │   ├── notification_port.py          # INotificationSender (WhatsApp, SMS, Push)
│   │   │   ├── ai_extraction_port.py         # IAiExtractionEngine (Gemini, local NLP)
│   │   │   ├── document_renderer_port.py     # IDocumentRenderer (PDF, PNG chart generator)
│   │   │   ├── event_bus_port.py             # IEventBus (Publish/Subscribe canonical events)
│   │   │   └── object_storage_port.py        # IObjectStorage (S3 file upload/download)
│   │   │
│   │   └── services/                         # Cross-cutting application domain services
│   │       ├── __init__.py
│   │       ├── metrics_calculator.py         # Deterministic TIR, fasting, PPBG aggregation
│   │       └── nutrition_service.py          # Deterministic katori volume to carb/GI estimation
│   │
│   ├── infrastructure/                       # ADAPTERS & EXTERNAL DRIVERS (Hexagonal Adapters)
│   │   ├── __init__.py
│   │   ├── persistence/                      # PostgreSQL + TimescaleDB + SQLAlchemy 2.x
│   │   │   ├── __init__.py
│   │   │   ├── database.py                   # Async engine, session factory, base declarative model
│   │   │   ├── models/                       # SQLAlchemy 2.x ORM table mappings
│   │   │   │   ├── __init__.py
│   │   │   │   ├── tenant_models.py          # Organizations, Facilities
│   │   │   │   ├── user_models.py            # Users, Roles, Memberships
│   │   │   │   ├── patient_models.py         # PatientProfiles, Caregivers, AvoidItems
│   │   │   │   ├── care_plan_models.py       # CarePlans, MedicationPlans, Targets
│   │   │   │   └── event_models.py           # Canonical event log table / Timescale hypertable
│   │   │   ├── repositories/                 # SQLAlchemy concrete repository implementations
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sql_patient_repo.py
│   │   │   │   ├── sql_event_store_repo.py
│   │   │   │   └── sql_care_plan_repo.py
│   │   │   └── alembic/                      # Database migrations
│   │   │       ├── env.py
│   │   │       ├── script.py.mako
│   │   │       └── versions/
│   │   │
│   │   ├── identity/                         # Keycloak OIDC & PostgreSQL RLS
│   │   │   ├── __init__.py
│   │   │   ├── keycloak_client.py            # OIDC token verification & public key caching
│   │   │   ├── rls_context.py                # PostgreSQL session tenant_id / user_id context
│   │   │   └── token_validator.py            # JWT bearer token decoder & claims validator
│   │   │
│   │   ├── channel/                          # Communication channel adapters
│   │   │   ├── __init__.py
│   │   │   ├── whatsapp_cloud.py             # Meta Cloud API HTTP client
│   │   │   ├── whatsapp_simulator.py         # In-memory simulator for automated tests
│   │   │   └── hmac_verifier.py              # HMAC-SHA256 signature verifier for Meta webhooks
│   │   │
│   │   ├── ai/                               # Machine Learning & AI Adapters
│   │   │   ├── __init__.py
│   │   │   ├── gemini_client.py              # Google Gemini API connector (Draft extraction only)
│   │   │   ├── local_nlp_refiner.py          # Deterministic typo map & Hinglish phonetics
│   │   │   └── background_worker.py          # Decoupled intake worker polling stored events
│   │   │
│   │   ├── reporting/                        # Clinical Document Adapters
│   │   │   ├── __init__.py
│   │   │   ├── reportlab_pdf_adapter.py      # 2-Page clinical PDF generator (ReportLab 4.x)
│   │   │   ├── matplotlib_chart_adapter.py   # Glycemic curve & slot charts (Matplotlib 3.8+)
│   │   │   └── html_preview_adapter.py       # Web preview renderer
│   │   │
│   │   ├── storage/                          # Object storage adapter
│   │   │   ├── __init__.py
│   │   │   ├── s3_adapter.py                 # S3 / MinIO client for photo and PDF storage
│   │   │   └── local_storage_adapter.py      # Fallback local filesystem storage adapter
│   │   │
│   │   └── cache/                            # Redis caching & messaging adapter
│   │       ├── __init__.py
│   │       ├── redis_client.py               # Redis connection manager & cache helper
│   │       └── redis_event_bus.py            # Redis pub/sub or stream event bus adapter
│   │
│   ├── interfaces/                           # INBOUND DRIVING CONTROLLERS (HTTP, Webhook, CLI)
│   │   ├── __init__.py
│   │   ├── http/                             # FastAPI Web Application & Routers
│   │   │   ├── __init__.py
│   │   │   ├── app.py                        # FastAPI application factory (`create_app`)
│   │   │   ├── middleware/                   # Request pipeline middleware
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth_middleware.py        # Keycloak JWT extraction & context population
│   │   │   │   ├── security_headers.py       # HSTS, CSP, CORS configuration
│   │   │   │   └── error_handlers.py         # Global domain exception to HTTP mapping
│   │   │   │
│   │   │   └── v2/                           # Enterprise API v2 (Role-aware, multi-tenant)
│   │   │       ├── __init__.py
│   │   │       ├── auth_router.py            # OIDC callback & token refresh
│   │   │       ├── patient_router.py         # Patient profile, targets, and care team
│   │   │       ├── observation_router.py     # Glucose observations & meal logs
│   │   │       ├── care_plan_router.py       # Care plan & medication management (Clinician)
│   │   │       ├── report_router.py          # Clinical summary & PDF report generation
│   │   │       ├── task_router.py            # Care coordinator / nurse workflow tasks
│   │   │       ├── admin_router.py           # Organization & facility provisioning
│   │   │       └── webhook_router.py         # Meta WhatsApp webhook (HMAC-SHA256 verified)
│   │   │
│   │   └── cli/                              # Command-line tools
│   │       ├── __init__.py
│   │       ├── seed_cli.py                   # Multi-tenant demo dataset seeder
│   │       └── worker_cli.py                 # Background intake worker runner
│   │
│   └── compatibility/                        # AAHAAR LEGACY RETRO-COMPATIBILITY BRIDGE
│       ├── __init__.py
│       ├── legacy_store_adapter.py           # Adapts legacy `Store` calls to SQLite during transition
│       ├── legacy_v1_router.py               # Emulates `/api/v1/*` endpoints for baseline clients
│       ├── legacy_whatsapp_bridge.py         # Connects legacy WhatsApp webhook paths to new intake
│       └── legacy_report_bridge.py           # Routes legacy `/api/v1/patients/{id}/report` to new ports
│
├── config/                                   # Typed configuration management
│   ├── __init__.py
│   ├── settings.py                           # Pydantic v2 BaseSettings with typed env vars
│   └── constants.py                          # Clinical thresholds, katori ml values, regex maps
│
├── scripts/                                  # Automation and migration operations
│   ├── init_git_baseline.sh                  # Git repository initialization script
│   ├── run_legacy_tests.sh                   # Script running the 57 baseline tests
│   ├── migrate_sqlite_to_postgres.py         # One-way data migrator from aahaar.db to PostgreSQL
│   └── seed_enterprise_demo.py               # Enterprise multi-tenant scenario seeder
│
└── tests/                                    # Unified Test Framework
    ├── conftest.py                           # Root pytest fixtures (async clients, DB fixtures)
    │
    ├── legacy/                               # EXACT 57 BASELINE TESTS (Preserved without modification)
    │   ├── conftest.py                       # Legacy fixtures (tmp SQLite store, config)
    │   ├── test_linking.py                   # 16 Baseline linking tests
    │   └── test_pipeline.py                  # 41 Baseline pipeline tests
    │
    ├── unit/                                 # PURE DOMAIN & APPLICATION UNIT TESTS
    │   ├── test_glucose_value.py             # 20-600 mg/dL sanity rules
    │   ├── test_katori_portions.py           # Volumetric katori calculations
    │   ├── test_asymmetry_rules.py           # Carbs/GI leakage prevention tests
    │   └── test_two_number_rule.py           # Patient/Caregiver authentication checks
    │
    ├── integration/                          # INFRASTRUCTURE INTEGRATION TESTS
    │   ├── test_postgres_repos.py            # PostgreSQL repository CRUD & RLS tests
    │   ├── test_redis_cache.py               # Redis caching and invalidation tests
    │   └── test_hmac_webhook.py              # HMAC-SHA256 verification tests
    │
    └── api/                                  # ENDPOINT CONTRACT TESTS
        ├── test_v1_compatibility.py          # Regression tests for `/api/v1` compatibility
        └── test_v2_endpoints.py              # New `/api/v2` role-aware endpoint tests
```

---

## 3. File Migration Matrix

The following matrix documents the disposition, new location, architectural action, import/dependency impacts, test impacts, and migration sequence order for every file currently in the repository.

### Action Legend
- **KEEP**: File remains in current functional shape with no internal logic rewrites.
- **MOVE**: File relocated to new architectural folder; internal imports updated.
- **WRAP**: File wrapped in an adapter interface to isolate callers from implementation details.
- **SPLIT**: File partitioned into distinct single-responsibility modules (e.g., separating domain from persistence).
- **MERGE**: File combined with adjacent functionality to eliminate redundancy.
- **DEPRECATE**: File marked for eventual phase-out; preserved during transition via compatibility bridge.
- **REPLACE**: File replaced by a superior enterprise standard (e.g., Pydantic v2 `BaseSettings` replacing raw dataclass).
- **REMOVE**: Obsolete asset discarded after transition is complete.

---

### File-by-File Matrix

| # | Old Path | New Path | Action | Import Impact | Dependency Impact | Test Impact | Order |
| :---: | :--- | :--- | :---: | :--- | :--- | :--- | :---: |
| 1 | `app/__init__.py` | `backend/__init__.py` | **MOVE** | Top-level package name changes from `app` to `backend` | None | Baseline tests import `app`; shim required | Phase 1 |
| 2 | `app/config.py` | `config/settings.py` | **REPLACE** | Replace `dataclass` with `pydantic_settings.BaseSettings`; provide `app.config.Settings` backward-compatible alias | Requires `pydantic-settings` | All 57 tests depend on `Settings`; alias must preserve identical attribute names | Phase 2 |
| 3 | `app/core/__init__.py` | `backend/domain/__init__.py` | **MOVE** | None | None | None | Phase 1 |
| 4 | `app/core/ai.py` | `backend/infrastructure/ai/local_nlp_refiner.py` & `backend/infrastructure/ai/gemini_client.py` | **SPLIT** | Split local regex typo map from external Gemini/Groq LLM caller; eliminate global `_last_ai_status` | Moves external API calls to infrastructure adapter | Exercised by `test_typo_correction_and_talking_back_ai`, `test_natural_language_glucose_reading` | Phase 3 |
| 5 | `app/core/ai_worker.py` | `backend/infrastructure/ai/background_worker.py` | **WRAP** | Decouple from direct SQLite `Store`; inject `ICanonicalEventRepository` and `INotificationSender` | None | Exercised by 7 intake worker tests in `test_pipeline.py` | Phase 4 |
| 6 | `app/core/datamodel.py` | `backend/infrastructure/persistence/legacy_sqlite_store.py` & `backend/infrastructure/persistence/models/*` | **SPLIT** | Separate SQLite `Store` (retained for legacy tests) from new SQLAlchemy 2.0 PostgreSQL domain models | Introduces `sqlalchemy>=2.0` and `alembic` | `conftest.py` initializes `Store(tmp_path / "test.db")`; SQLite store must remain functional | Phase 2 |
| 7 | `app/core/escalation.py` | `backend/application/commands/evaluate_escalations.py` | **WRAP** | Wrap `due_escalations` into application command handler; isolate store dependency | None | Exercised by `test_escalation_idempotent_and_daily_cap` | Phase 3 |
| 8 | `app/core/intake_ai.py` | `backend/application/services/intake_ai_service.py` | **WRAP** | Extract raw string formatting into domain DTOs; route follow-up questions through notification port | None | Exercised by `test_intake_local_notifier_asks_for_missing`, `test_intake_never_medical_advice` | Phase 3 |
| 9 | `app/core/metrics.py` | `backend/application/services/metrics_calculator.py` | **WRAP** | Retain pure calculation formulas (`tir_pct`, `fasting_stats`, `ppbg_stats`); decouple from `Store` query | None | Exercised by `test_tir_classification_70_180`, `test_weekday_weekend_ppbg_split`, `test_post_slot_stats_split_weekday_weekend` | Phase 2 |
| 10 | `app/core/nutrition.py` | `backend/domain/value_objects/meal_portion.py` & `backend/application/services/nutrition_service.py` | **SPLIT** | Separate immutable katori definitions and carb/GI lookup catalogs from parsing helpers | None | Exercised by `test_portion_correction_applies`, `test_only_confirmed_meals_count` | Phase 2 |
| 11 | `app/core/parse.py` | `backend/application/services/inbound_parser.py` | **WRAP** | Wrap parsing logic; remove deferred circular imports (`from .ai import refine_text_local`); pure functional parsing | None | Exercised by `test_parse_reading_from_text`, `test_parse_out_of_range_reading_refused`, `test_prick_keyword_parsing` | Phase 2 |
| 12 | `app/core/process.py` | `backend/application/commands/ingest_message.py` | **SPLIT** | Split `IngestService` into pure command handlers; eliminate auto-bind vulnerability (`app/core/process.py:65-74`) | None | Exercised by `test_two_number_rule`, `test_unregistered_number_refused`, `test_reading_sanity_guard` | Phase 3 |
| 13 | `app/core/report.py` | `backend/application/queries/get_clinical_report.py` | **WRAP** | Wrap `build_report_context` to output typed `ReportContextDTO`; enforce non-diagnostic language rules | None | Exercised by `test_report_context_has_no_forbidden_language`, `test_chart_context_has_three_slot_series` | Phase 3 |
| 14 | `app/core/seed.py` | `backend/interfaces/cli/seed_cli.py` & `scripts/seed_real.py` | **MOVE** | Move synthetic demo generator; maintain compatibility signature `seed_demo(store, cfg, ...)` | None | Fixture `seeded` in `conftest.py` depends on `seed_demo` | Phase 2 |
| 15 | `app/report/__init__.py` | `backend/infrastructure/reporting/__init__.py` | **MOVE** | Package init relocation | None | None | Phase 1 |
| 16 | `app/report/charts.py` | `backend/infrastructure/reporting/matplotlib_chart_adapter.py` | **WRAP** | Wrap Matplotlib generator behind `IChartRendererPort`; decouple from filesystem writes | `matplotlib>=3.8` | Exercised by `test_chart_context_has_three_slot_series`, `scripts/demo.py` | Phase 3 |
| 17 | `app/report/html_preview.py` | `backend/infrastructure/reporting/html_preview_adapter.py` | **MOVE** | Move HTML report preview generator; encapsulate HTML escaping | None | Consumed by report endpoint `/api/v1/patients/{id}/preview.html` | Phase 3 |
| 18 | `app/report/pdf.py` | `backend/infrastructure/reporting/reportlab_pdf_adapter.py` | **WRAP** | Wrap ReportLab 2-page PDF generator behind `IDocumentRendererPort` | `reportlab>=4.0`, `pillow` | Exercised by `test_pdf_structure` (in demo script), `test_pipeline.py` imports `_deltastr` | Phase 3 |
| 19 | `app/server/__init__.py` | `backend/interfaces/http/__init__.py` | **MOVE** | Package init relocation | None | None | Phase 1 |
| 20 | `app/server/main.py` | `backend/interfaces/http/app.py` & `backend/compatibility/legacy_v1_router.py` | **SPLIT** | Split monolithic 622-line file into FastAPI app factory, v1 compatibility router, and middleware | Eliminates global `_webhook_history` mutable state | `app.server.main.create_app` is imported by `test_linking.py` and `test_pipeline.py` | Phase 4 |
| 21 | `app/server/whatsapp.py` | `backend/infrastructure/channel/whatsapp_cloud.py` & `backend/infrastructure/channel/whatsapp_simulator.py` | **SPLIT** | Separate Cloud API client from Simulator; add HMAC-SHA256 signature verification | None | Exercised by webhook and outbound tests | Phase 4 |
| 22 | `app/static/app.js` | `apps/legacy-dashboard/app.js` | **MOVE** | Relocate to legacy dashboard app; mount as static asset for legacy/debug access | None | Purely client-side browser script | Phase 5 |
| 23 | `app/static/index.html` | `apps/legacy-dashboard/index.html` | **MOVE** | Relocate to legacy dashboard app | None | Purely client-side HTML structure | Phase 5 |
| 24 | `app/static/style.css` | `apps/legacy-dashboard/style.css` | **MOVE** | Relocate to legacy dashboard app | None | Purely client-side stylesheet | Phase 5 |
| 25 | `docs/WHATSAPP_DEMO.md` | `docs/WHATSAPP_DEMO.md` | **KEEP** | Retain as operational guide for Meta Cloud API onboarding | None | None | Phase 1 |
| 26 | `scripts/analyze_stored.py` | `scripts/analyze_stored.py` | **WRAP** | Update imports to use compatibility shim or new application query | None | Utility script | Phase 5 |
| 27 | `scripts/demo.py` | `scripts/demo.py` | **WRAP** | Update imports to use compatibility shim or new application query | None | Utility script | Phase 5 |
| 28 | `scripts/seed_real.py` | `scripts/seed_real.py` | **WRAP** | Update imports to use compatibility shim or new application query | None | Utility script | Phase 5 |
| 29 | `tests/conftest.py` | `tests/conftest.py` & `tests/legacy/conftest.py` | **KEEP** | Keep root conftest for baseline suite; add root fixtures for new test suites | None | Direct dependency for all 57 tests | Phase 1 |
| 30 | `tests/test_linking.py` | `tests/legacy/test_linking.py` | **KEEP** | Retain all 16 tests untouched; verify against legacy compatibility layer | None | Must pass 16/16 tests | Phase 1 |
| 31 | `tests/test_pipeline.py` | `tests/legacy/test_pipeline.py` | **KEEP** | Retain all 41 tests untouched; verify against legacy compatibility layer | None | Must pass 41/41 tests | Phase 1 |
| 32 | `pytest.ini` | `pytest.ini` | **KEEP** | Maintain `pythonpath = .` and `testpaths = tests` | None | Direct test runner config | Phase 1 |
| 33 | `requirements.txt` | `requirements.txt` | **WRAP** | Keep current 8 packages; prepare requirements for PostgreSQL, SQLAlchemy, Alembic | None | Packaging config | Phase 2 |
| 34 | `.gitignore` | `.gitignore` | **KEEP** | Ensure `.db`, `.venv`, `reports/` remain ignored; add Node/Expo ignores | None | Git hygiene | Phase 1 |
| 35 | `LICENSE` | `LICENSE` | **KEEP** | Retain MIT license | None | Legal | Phase 1 |
| 36 | `README.md` | `README.md` | **KEEP** | Master architectural documentation | None | Documentation | Phase 1 |
| 37 | SQLite DB files | `aahaar.db`, `aahaar-demo.db` | **KEEP** | Retain in root for legacy execution; target for migration script in Gate 03 | None | Local persistence | Phase 1 |

---

## 4. Compatibility Boundary Architecture

To guarantee zero regression of existing Aahaar capabilities while enterprise infrastructure is introduced, a **Compatibility Boundary Layer** is established.

### 4.1 Compatibility Bridge Architecture Diagram

```
+---------------------------------------------------------------------------------+
|                           EXTERNAL CLIENTS & CONSUMERS                          |
|  (WhatsApp Webhook / Simulator / Legacy JS Dashboard / Baseline Pytest Suite)   |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                       LEGACY API COMPATIBILITY ADAPTER                          |
|                       `backend/compatibility/legacy_v1_router.py`              |
|                                                                                 |
|   POST /api/v1/inbound                  POST /api/v1/webhooks/whatsapp          |
|   GET  /api/v1/patients/{id}/metrics    GET  /api/v1/patients/{id}/report       |
|   POST /api/v1/patients/{id}/report/build                                       |
+---------------------------------------------------------------------------------+
                         |                                |
                         v                                v
+-----------------------------------+    +----------------------------------------+
|   LEGACY STORE ADAPTER            |    |   APPLICATION COMMAND / QUERY BUS      |
|   `legacy_store_adapter.py`       |    |   `backend/application/`               |
|                                   |    |                                        |
|   * Wraps SQLite `Store`          |    |   * Dispatches IngestCommand           |
|   * Maps integer `patient_id`     |    |   * Dispatches QueryMetrics            |
|   * Emulates raw SQL queries      |    |   * Generates Canonical Events         |
+-----------------------------------+    +----------------------------------------+
         |                                                 |
         v                                                 v
+------------------+                             +--------------------------------+
|  LEGACY STORAGE  |                             |     ENTERPRISE INFRASTRUCTURE  |
|  `aahaar.db`     |                             |     PostgreSQL / TimescaleDB   |
|  (SQLite 3)      |                             |     Keycloak / Redis / S3      |
+------------------+                             +--------------------------------+
```

### 4.2 Isolation Strategies

1. **Legacy SQLite Isolation (`LegacyStoreAdapter`)**:
   - The monolithic `app/core/datamodel.py:Store` class remains active during Phase 1 under `backend/infrastructure/persistence/legacy_sqlite_store.py`.
   - An import hook in `app/core/datamodel.py` delegates to this legacy store adapter so that any existing script or test importing `from app.core.datamodel import Store` continues to instantiate the exact same SQLite engine without modification.
   - New domain code never imports `Store`; it interacts exclusively with `IPatientRepository` and `ICanonicalEventRepository`.

2. **Legacy Patient Identity Isolation**:
   - Baseline Aahaar identifies patients via sequential integer primary keys (`patient_id = 1`) and raw phone numbers (`+919000000001`).
   - The target architecture uses UUID aggregate roots with tenant partitioning (`tenant_id`, `facility_id`, `user_id`).
   - The compatibility layer maintains an in-memory or lookup translation table:
     $$\text{UUID} \longleftrightarrow \text{Legacy integer ID}$$
   - When a legacy request arrives at `/api/v1/patients/1/metrics`, the adapter maps `1` to the default tenant's primary patient UUID, executes the query through the application layer, and formats the output back into the legacy integer-keyed JSON shape.

3. **Legacy API Handler Isolation**:
   - The 622 lines of `app/server/main.py` are preserved via an adapter router (`legacy_v1_router.py`) mounted at `/api/v1` in the new FastAPI app.
   - All legacy response envelopes, HTTP status codes, and error formats are preserved bit-for-bit, satisfying all assertions in `test_linking.py` and `test_pipeline.py`.
   - New enterprise endpoints will be mounted exclusively under `/api/v2/`.

4. **Legacy Report Generation Isolation**:
   - `app/report/pdf.py` and `app/report/charts.py` are wrapped inside `ReportLabPdfAdapter` and `MatplotlibChartAdapter`.
   - The legacy endpoint `POST /api/v1/patients/{id}/report/build` calls this adapter, generating the exact 2-page A4 PDF layout without altering any visual coordinates or font configurations.

5. **Legacy WhatsApp Processing Isolation**:
   - Inbound webhook payloads from Meta WhatsApp or the simulator continue to be accepted at `POST /api/v1/webhooks/whatsapp`.
   - The handler stores the raw message first (preserving the store-first defense tested in `test_webhook_store_first_duplicate_skip`), then emits a canonical event.

---

## 5. Import Dependency Analysis

A comprehensive AST-based import analysis was conducted across all 22 Python modules. The analysis revealed seven distinct forms of structural coupling that must be resolved.

### 5.1 Identified Couplings & Leakages

```
[ app/server/main.py ]  ----(instantiates at import)----> [ Settings dataclass ]
         |
         +----(direct instantiation)----> [ IngestService(store, settings) ]
         |                                       |
         |                                       +----(raw SQL queries)----> [ SQLite Store ]
         |
         +----(in-memory mutable state)----> [ _webhook_history: list[dict] ]

[ app/core/parse.py ] <====(deferred import inside _items)====> [ app/core/nutrition.py ]
         ^
         +====(deferred import inside parse_inbound)=====> [ app/core/ai.py ]
                                                                  |
[ app/core/intake_ai.py ] <---(imports mutable global state)------+ (_last_ai_status)
```

1. **Circular & Deferred Imports**:
   - `app/core/parse.py:126`: Inside `parse_inbound`, deferred import `from .ai import refine_text_local` is used to avoid circular loading.
   - `app/core/parse.py:262, 277`: Inside `_items` and `_mock_photo`, deferred imports `from .nutrition import estimate_carbs_g, classify_text, KATORI_LABELS` are used.
   - `app/core/intake_ai.py:38`: Inside `_meal_items`, deferred import `from .parse import _items` is used.
   - *Resolution*: Move typo maps and string normalizers into a pure utility module (`backend/domain/value_objects/`); pass dependencies as parameters rather than importing across sibling core modules.

2. **Database Leakage into Domain**:
   - `app/core/datamodel.py` mixes SQLite DDL (`SCHEMA`), connection context managers, raw SQL strings (`SELECT * FROM patients WHERE id = ?`), and business logic.
   - Domain processing services (`IngestService`, `compute_window_metrics`, `due_escalations`) require direct instances of `Store`.
   - *Resolution*: Introduce repository interfaces (`IPatientRepository`, `ICanonicalEventRepository`). Services receive interface abstractions; persistence details remain in `infrastructure/persistence/`.

3. **External API Leakage into Core**:
   - `app/core/ai.py` and `app/core/intake_ai.py` perform direct HTTP requests to Google Gemini and Groq via `urllib.request`.
   - *Resolution*: Encapsulate all external AI network communication behind `IAiExtractionEngine` in `backend/infrastructure/ai/`.

4. **Framework Leakage into Domain**:
   - `app/server/main.py` directly coordinates domain logic, background tasks, and file generation within route handlers.
   - *Resolution*: FastApi route handlers become thin controllers that convert HTTP requests into Application Commands/Queries and return Pydantic DTO responses.

5. **Static Global State**:
   - `app/server/main.py:32`: `settings: Settings = get_settings()` instantiated at module import time.
   - `app/server/main.py:44`: `_webhook_history: list[dict] = []` mutable global list.
   - `app/core/ai.py:59`: `_last_ai_status: dict = {"configured": False, ...}` mutable global dictionary.
   - *Resolution*: Inject configuration via FastAPI dependency injection (`Depends(get_settings)`); store webhook histories and AI status in Redis or the audit log repository.

6. **Configuration Coupling**:
   - `app/config.py:Settings` bundles database paths (`aahaar.db`), clinical thresholds (`glucose_low = 70.0`), operational nudges (`esc_hour = 21`), katori volumes, and feature flags into a single monolithic object.
   - *Resolution*: Segregate into `DomainClinicalConstants` (immutable medical rules) and `BackendInfrastructureSettings` (database URLs, API keys, cache ports).

### 5.2 Dependency Decoupling Sequence

The uncoupling must occur in the following strictly ordered sequence:

```
Step 1: Extract Pure Value Objects & Domain Constants
        (No dependencies on DB, FastAPI, or Settings)
                          │
                          ▼
Step 2: Introduce Repository Interfaces & Outbound Ports
        (Abstract contracts for DB, AI, Notifications, Storage)
                          │
                          ▼
Step 3: Refactor Core Parsing & Nutrition as Stateless Functions
        (Eliminate deferred circular imports in parse.py and nutrition.py)
                          │
                          ▼
Step 4: Implement Infrastructure Adapters for SQLite & External APIs
        (Wrap legacy Store behind IPatientRepository)
                          │
                          ▼
Step 5: Decouple Global State into Injected Services
        (Replace _webhook_history and _last_ai_status with cache/repo calls)
                          │
                          ▼
Step 6: Refactor FastAPI Handlers to Thin Inbound Controllers
        (Move orchestration into application Commands/Queries)
```

---

## 6. Domain Boundary Definition

The boundary between domain, application, infrastructure, and interfaces is strictly enforced.

```
+-----------------------------------------------------------------------------------+
| INTERFACES LAYER                                                                  |
|   FastAPI Routers, Webhook Controllers, CLI Runners, Middleware                   |
+-----------------------------------------------------------------------------------+
                                         │  calls
                                         ▼
+-----------------------------------------------------------------------------------+
| APPLICATION LAYER                                                                 |
|   Commands, Queries, Application Services, DTOs, Outbound Port Interfaces         |
+-----------------------------------------------------------------------------------+
                                         │  uses
                                         ▼
+-----------------------------------------------------------------------------------+
| DOMAIN LAYER (CORE)                                                               |
|   Entities, Value Objects, Canonical Events, Invariants, Repository Interfaces    |
|   * ZERO external dependencies (No FastAPI, No SQLAlchemy, No Redis, No HTTP)     |
+-----------------------------------------------------------------------------------+
                                         ▲  implements
                                         │
+-----------------------------------------------------------------------------------+
| INFRASTRUCTURE LAYER                                                              |
|   SQLAlchemy 2.x, PostgreSQL, Redis, Keycloak, S3, Meta WhatsApp, ReportLab       |
+-----------------------------------------------------------------------------------+
```

### 6.1 Layer Ownership Specifications

#### 1. Domain Layer (`backend/domain/`)
- **Entities**:
  - `User`: Identity, authentication reference (Keycloak sub), status, primary role.
  - `Organization` & `Facility`: Multi-tenant boundary roots.
  - `PatientProfile`: Clinical baseline, enrollment date, active status.
  - `CarePlan`: Clinician-assigned glycemic targets, logging window duration.
  - `MedicationPlan`: Clinician-authored prescription directives (**Strictly read-only for AI & patients**).
  - `CareTeamMembership`: Clinician-to-patient assignment with relationship-aware permissions.
  - `CaregiverRelationship`: Patient-to-caregiver proxy authorization.
- **Value Objects**:
  - `GlucoseMeasurement`: Value in mg/dL, validated strictly within $[20, 600]$.
  - `MealPortion`: Katori sizing (`'s'` = 150 ml, `'m'` = 220 ml, `'l'` = 350 ml).
  - `ReadingTag`: Categorical context (`fasting`, `pre`, `postprandial`, `postbreakfast`, `postlunch`, `postdinner`).
  - `PhoneNumber`: E.164 formatted string.
  - `UHID`: Unique Healthcare Identifier string.
- **Canonical Domain Events**:
  - `ObservationGlucoseLoggedEvent`: Immutable blood sugar event.
  - `IntakeMealLoggedEvent`: Draft meal photo/text logged.
  - `MealPortionConfirmedEvent`: Patient-confirmed volumetric portion.
  - `MedicationAdministeredEvent`: Patient-logged medication intake.
  - `EscalationTriggeredEvent`: 9 PM missed-logging notification event.
- **Invariants & Domain Rules**:
  - Sanity check: $20.0 \le \text{glucose} \le 600.0$ mg/dL; out-of-range values trigger refusal.
  - Two-number rule: Inbound logging accepted only from linked patient or active caregiver.
  - Information asymmetry: Calculated carbohydrates and glycemic index are strictly forbidden in patient-facing payloads.
  - Daily escalation limit: Maximum 1 missed-logging escalation per patient per calendar day.
  - Non-diagnostic boundary: AI models are strictly prohibited from generating medical advice, diagnosis, or medication adjustments.

#### 2. Application Layer (`backend/application/`)
- **Use Cases & Commands**:
  - `IngestGlucoseReadingCommand`: Validates value, logs canonical event, triggers optional caregiver alert.
  - `LogMealDraftCommand`: Extracts candidate dishes, saves draft, prepares patient confirmation prompt.
  - `ConfirmMealPortionCommand`: Updates meal status to `confirmed`, calculates deterministic carbs/GI.
  - `LogMedicationAdminCommand`: Records dose timestamp against active `MedicationPlan`.
  - `EvaluateEscalationsCommand`: Evaluates patient logging adherence at 21:00 and schedules notifications.
- **Queries**:
  - `ComputeWindowMetricsQuery`: Calculates TIR ($70-180$ mg/dL), fasting mean, weekday vs. weekend PPBG.
  - `BuildClinicalReportContextQuery`: Assembles 14-day glycemic profile, meal correlation, and charts for clinician review.
- **Outbound Ports**:
  - `INotificationSender`, `IAiExtractionEngine`, `IDocumentRenderer`, `IObjectStorage`, `IEventBus`.

#### 3. Infrastructure Layer (`backend/infrastructure/`)
- **Adapters**:
  - `PostgresPatientRepository`, `TimescaleEventStoreRepository`.
  - `KeycloakTokenValidator`, `PostgresRLSManager`.
  - `MetaWhatsAppCloudClient`, `SimulatorWhatsAppClient`, `HmacSignatureVerifier`.
  - `GeminiExtractionAdapter`, `LocalHinglishNlpAdapter`.
  - `ReportLabPdfAdapter`, `MatplotlibChartAdapter`.
  - `S3StorageAdapter`, `RedisCacheAdapter`.
  - `LegacySqliteStoreAdapter` (backward-compatibility bridge).

#### 4. Interfaces Layer (`backend/interfaces/`)
- **Controllers & Entrypoints**:
  - FastAPI Web Application (`create_app`).
  - Route Handlers: `/api/v2/*` (enterprise), `/api/v1/*` (compatibility), `/api/admin/*` (console).
  - Middleware: JWT authentication, security headers, correlation ID logging.
  - CLI commands: `seed_enterprise_demo`, `run_intake_worker`.

---

## 7. Test Preservation Strategy

The baseline test suite comprises **57 tests across 2 test files**, all currently passing with 0 failures:
- `tests/test_linking.py`: 16 tests (Operator key security, phone linking, Meta webhook processing).
- `tests/test_pipeline.py`: 41 tests (Parsing, confirmation loop, TIR calculation, AI worker, audit defenses).

### 7.1 Preservation Invariant

> [!IMPORTANT]
> At every stage of repository restructuring and scaffolding, the existing command:
> ```bash
> .venv/bin/pytest tests -q
> ```
> **MUST pass with 57 passed, 0 failures.**
> Existing test files will not be deleted, renamed, or modified during initial scaffolding.

### 7.2 Test Suite Architecture

```
tests/
│
├── conftest.py                       # Root fixtures (preserves store, cfg, seeded fixtures)
│
├── legacy/                           # EXACT BASELINE TESTS (Target for mirrored execution)
│   ├── conftest.py                   # Legacy SQLite fixtures
│   ├── test_linking.py               # 16 Baseline linking tests
│   └── test_pipeline.py              # 41 Baseline pipeline tests
│
├── unit/                             # NEW DOMAIN UNIT TESTS
│   ├── domain/
│   │   ├── test_glucose_vo.py        # Glucose sanity range (20-600) invariants
│   │   ├── test_katori_vo.py         # Katori volume (150/220/350 ml) invariants
│   │   └── test_asymmetry_rules.py   # Assert patient echoes NEVER contain carbs/GI
│   └── application/
│       ├── test_ingest_command.py    # Command handler tests with mocked ports
│       └── test_metrics_service.py   # TIR and PPBG slot calculation verification
│
├── integration/                      # NEW INFRASTRUCTURE INTEGRATION TESTS
│   ├── test_sqlalchemy_models.py     # SQLAlchemy 2.0 schema & relationship tests
│   ├── test_timescale_events.py      # Canonical event append-only store tests
│   ├── test_redis_cache.py           # Redis session & caching tests
│   └── test_hmac_webhook.py          # Meta webhook HMAC-SHA256 signature verification
│
├── api/                              # NEW API CONTRACT TESTS
│   ├── test_v1_backwards_compat.py   # Verify /api/v1 compatibility routes
│   ├── test_v2_patient_api.py        # Verify /api/v2 role-aware patient routes
│   └── test_v2_admin_api.py          # Verify /api/v2 multi-tenant admin routes
│
└── security/                         # NEW SECURITY & AUDIT TESTS
    ├── test_rls_tenant_isolation.py  # Verify PostgreSQL Row Level Security
    ├── test_keycloak_jwt_roles.py    # Verify RBAC claim extraction from JWTs
    └── test_autobind_eliminated.py   # Verify unknown phone numbers cannot bind to patient
```

### 7.3 Mapping Existing 57 Tests to Architectural Concerns

| Baseline Test Category | Test Count | Existing Coverage | Future Architectural Mapping |
| :--- | :---: | :--- | :--- |
| **Phone Linking & Identity** | 8 | Operator key required, phone relinking, 2-number rule enforcement, garbage phone rejection | Maps to `LinkPatientPhoneCommand` and `CaregiverRelationship` domain invariant tests |
| **Inbound Parsing & Sanity** | 7 | Glucose parsing, 20-600 mg/dL sanity checks, natural language regex, typo correction | Maps to `GlucoseMeasurement` Value Object and `InboundParser` service tests |
| **Confirmation Loop** | 5 | Meal pending state, portion confirmation, portion correction, unconfirmed meal exclusion | Maps to `MealPortionConfirmedEvent` and `LogMealDraftCommand` tests |
| **Glycemic Analytics (TIR)** | 6 | 70-180 mg/dL TIR classification, fasting stats, weekend/weekday PPBG split, slot inference | Maps to `MetricsCalculator` application service tests |
| **Clinical Safety & Asymmetry** | 3 | Forbidden language suppression, patient reply carb/GI exclusion, medical advice prohibition | Maps to `PatientFacingDTO` projection and domain guard tests |
| **Operational Escalation** | 1 | 9 PM missed-logging escalation idempotency, daily nudge cap | Maps to `EvaluateEscalationsCommand` application tests |
| **AI Intake Worker** | 11 | Store-first webhook persistence, offline worker row polling, duplicate suppression, ambiguous reading resolution | Maps to `BackgroundIntakeWorker` and `IAiExtractionEngine` integration tests |
| **Webhook Infrastructure** | 16 | Background webhook task processing, event persistence across restart, duplicate skipping | Maps to `MetaWebhookRouter` and `HmacSignatureVerifier` interface tests |
| **Total Baseline Tests** | **57** | **100% Passing Baseline** | **Maintained continuously via compatibility bridge** |

---

## 8. Git Safety & Version Control Strategy

### 8.1 Critical Inspection Finding

> [!CAUTION]
> Direct execution of `git status`, `git branch -a`, and `git log` on `/Users/subhamdas/Documents/health-a-thon-BioCypher--master` returned:
> ```
> fatal: not a git repository (or any of the parent directories): .git
> ```
> The codebase was extracted from an archive without an initialized `.git` tracking directory. No commit history or baseline snapshot currently exists on disk.

### 8.2 Baseline Initialization Protocol (Gate 02B Prerequisite)

Before any file is created, moved, or modified, a formal Git baseline must be established using the following exact sequence:

```bash
# 1. Initialize local git repository
git init

# 2. Configure identity for migration traceability
git config user.name "Antigravity Architecture Engine"
git config user.email "engineering@thali-plate.internal"

# 3. Stage all verified baseline files
git add .

# 4. Commit baseline snapshot
git commit -m "chore(baseline): freeze verified Aahaar prototype at Gate 00/01 baseline (57 passing tests)"

# 5. Create immutable baseline tag
git tag -a baseline-gate-00 -m "Verified baseline snapshot: 57 tests passing, pristine Aahaar codebase"
```

### 8.3 Target Branching Strategy

```
main (Protected: Always green 57/57 tests, verified production releases)
  │
  ├── develop (Active integration branch)
  │     │
  │     ├── feature/gate-02-scaffolding        <-- IMMEDIATE NEXT GATE
  │     │     (Directory tree skeleton, compatibility shims, packaging)
  │     │
  │     ├── feature/gate-03-domain-models
  │     │     (Pure domain entities, value objects, canonical events)
  │     │
  │     ├── feature/gate-04-database-alembic
  │     │     (PostgreSQL schemas, TimescaleDB hypertables, Alembic migrations)
  │     │
  │     ├── feature/gate-05-api-v2-keycloak
  │     │     (FastAPI v2 routers, Keycloak OIDC, HMAC webhook verifier)
  │     │
  │     └── feature/gate-06-mobile-admin-scaffold
  │           (Expo Universal Mobile app, Admin Web Console)
```

### 8.4 Rollback & Checkpoint Rules

- Every gate completion is marked by an annotated Git tag (e.g., `gate-02a-approved`, `gate-02b-scaffolding-complete`).
- In the event of a test regression during refactoring:
  ```bash
  git checkout -f feature/gate-02-scaffolding
  git clean -fd
  ```
- No branch may be merged into `develop` or `main` unless `.venv/bin/pytest tests -q` succeeds with zero errors.

---

## 9. Phased Migration Order

The migration proceeds across ten sequential, verifiable phases.

```
Phase 1: Git Baseline & Clean Architecture Skeleton
         Initialize Git, create directory layout, establish package shims.
         [Verification: 57 tests pass]
                          │
                          ▼
Phase 2: Configuration & Pure Domain Extraction
         Introduce Pydantic v2 settings, Value Objects (Glucose, Katori, Phone).
         [Verification: 57 tests pass + new Value Object unit tests pass]
                          │
                          ▼
Phase 3: Application Layer & Outbound Ports
         Implement Commands, Queries, and Port interfaces. Wrap core calculation routines.
         [Verification: 57 tests pass + new Application unit tests pass]
                          │
                          ▼
Phase 4: Compatibility Bridge Layer
         Deploy LegacyStoreAdapter and legacy v1 router. Decouple main.py.
         [Verification: 57 tests pass with ZERO direct dependencies on legacy main.py]
                          │
                          ▼
Phase 5: Infrastructure Layer (PostgreSQL, Redis, S3)
         Deploy SQLAlchemy 2.0 models, Alembic migrations, TimescaleDB event store.
         [Verification: Integration tests against test PostgreSQL container]
                          │
                          ▼
Phase 6: Enterprise API v2 & Security Hardening
         Deploy /api/v2 endpoints, Keycloak OIDC, HMAC-SHA256 webhook verification.
         [Verification: Security audit tests pass; HMAC reject tests pass]
                          │
                          ▼
Phase 7: Universal Mobile Application Scaffolding
         Initialize React Native + Expo monorepo under apps/mobile. Configure Drizzle ORM.
         [Verification: Mobile TypeScript build & local SQLite schema verification]
                          │
                          ▼
Phase 8: Admin Web Console Scaffolding
         Initialize Admin Web React SPA under apps/admin-web.
         [Verification: Admin web build & mock API integration pass]
                          │
                          ▼
Phase 9: Dual-Run Verification & Data Migration
         Execute migrate_sqlite_to_postgres.py; verify parity across databases.
         [Verification: Full end-to-end simulation comparison]
                          │
                          ▼
Phase 10: Legacy Deprecation & Cutover
          Decommission legacy static files and SQLite database; seal production v2.
          [Verification: Complete enterprise test suite pass]
```

---

## 10. Architectural & Operational Risks

| # | Risk Category | Severity | Probability | Impact Description | Mitigation Protocol |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **R-1** | **Untracked Working Tree Data Loss** | **CRITICAL** | High | Lack of `.git` directory means any erroneous file operation or accidental overwrite is irreversible. | **Mandatory Step 1 of Gate 02B**: Run `git init`, create baseline commit, and tag `baseline-gate-00` before creating or moving any file. |
| **R-2** | **Baseline Test Regression** | **HIGH** | Medium | Moving or renaming `app/server/main.py` or `app/core/datamodel.py` breaks import paths in `test_linking.py` and `test_pipeline.py`. | Maintain backward-compatible import shims in `app/` that re-export from `backend/` during the transition period. |
| **R-3** | **Circular Dependency Re-emergence** | **MEDIUM** | Medium | Re-importing between domain entities, value objects, and application commands causes Python `ImportError` on startup. | Strictly enforce the Dependency Rule: Domain imports nothing outside `backend/domain/`. Value Objects import no entities. |
| **R-4** | **SQLite to PostgreSQL Type Drift** | **HIGH** | Low | SQLite dynamically types `carbs REAL`, `ts TEXT`, `is_active INTEGER`. PostgreSQL strictly enforces schema types. | Define explicit Pydantic v2 schemas and SQLAlchemy 2.0 column types with UTC timestamp normalization and integer booleans. |
| **R-5** | **Clinical Information Asymmetry Leak** | **CRITICAL** | Low | Carbohydrate gram estimates or glycemic index values accidentally included in WhatsApp replies or mobile patient feeds. | Enforce strict projection separation: `PatientFacingDTO` models do not possess `carbs` or `gi` fields. Automated tests verify JSON serializations. |
| **R-6** | **Unauthenticated Webhook Vulnerability Window** | **HIGH** | Medium | Delaying HMAC-SHA256 signature verification leaves Meta webhook endpoint open to spoofed glucose payloads. | Deploy `HmacSignatureVerifier` middleware on the webhook route in Phase 6; reject all unsigned payloads in production mode. |
| **R-7** | **Global State Concurrency Collisions** | **MEDIUM** | High | `_webhook_history` in-memory list and module-level `settings` cause race conditions under multi-worker Uvicorn. | Eliminate module-level globals; use Redis for short-term webhook event logging and FastAPI dependency injection for settings. |

---

## 11. Gate 02B Prerequisites Checklist

Before proceeding to **GATE 02B — REPOSITORY SCAFFOLDING EXECUTION**, the following prerequisites must be confirmed:

- [x] **Audit Complete**: All files, sizes, line counts, and import relationships mapped.
- [x] **Architecture Approved**: Clean Architecture / Hexagonal layer ownership defined.
- [x] **Compatibility Layer Designed**: Isolation strategy for SQLite, patient identity, and legacy endpoints specified.
- [x] **Test Invariant Defined**: 57 baseline tests passing; zero test deletions permitted.
- [ ] **Git Initialization Approved**: User authorization to execute `git init` and tag `baseline-gate-00`.
- [ ] **Target Directory Approval**: User authorization to create directory skeletons (`backend/`, `apps/`, `config/`).
- [ ] **Dependencies Staged**: Readiness to add `pydantic-settings`, `sqlalchemy>=2.0`, and `alembic` to development environment.

---

## Final Status Declaration

```
================================================================================
GATE 02A STATUS: READY FOR SCAFFOLDING
================================================================================
```

The migration plan and repository map are completely specified. No files have been modified or deleted. The system is fully prepared to commence physical scaffolding under **GATE 02B**.
