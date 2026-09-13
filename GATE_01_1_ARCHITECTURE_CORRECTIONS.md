# GATE 01.1 — ARCHITECTURE RECONCILIATION CORRECTION PASS
## THALI × P.L.A.T.E. PRODUCTION MIGRATION PROGRAM
**Document Status:** Approved Architecture Corrections & Frozen Architectural Baseline  
**Gate Status:** READ-ONLY ARCHITECTURE CORRECTION (No source code, schema, or dependencies modified)

---

## 1. Corrections Applied

This document reconciles the findings of **GATE 00** and the initial design in **GATE 01** against the **already-frozen THALI × P.L.A.T.E. target architecture**. The following formal corrections have been applied:

```
+----------------------------------------------------------------------------------------------------+
|                                    CORRECTIONS SUMMARY MATRIX                                      |
+----+------------------------------+----------------------------------+-----------------------------+
| #  | Domain / Topic               | Gate 01 Initial Representation   | Corrected Frozen Decision   |
+----+------------------------------+----------------------------------+-----------------------------+
| 1  | Technology Stack             | Flagged mobile framework, IdP,   | FROZEN: React Native/Expo,  |
|    |                              | and storage as open decisions.   | Keycloak, S3, Drizzle/Expo  |
|    |                              |                                  | SQLite, FastAPI, PostgreSQL.|
+----+------------------------------+----------------------------------+-----------------------------+
| 2  | Application Phasing          | Included P.L.A.T.E. Web Work-    | REPHASED: Phase 1 is        |
|    |                              | station in Phase 1 scope.        | MOBILE-FIRST. P.L.A.T.E. Web|
|    |                              |                                  | is optional Phase 2.        |
+----+------------------------------+----------------------------------+-----------------------------+
| 3  | Legacy Dashboard Status      | Partially conflated static UI    | CLARIFIED: app/static/ is   |
|    |                              | with target web consoles.        | temporary legacy/debug only;|
|    |                              |                                  | distinct from Admin Web.    |
+----+------------------------------+----------------------------------+-----------------------------+
| 4  | Domain Entities vs. Events   | Abstracted all domain models as  | SEPARATED: Discrete Domain  |
|    |                              | a single canonical event schema. | Entities (Current State) vs.|
|    |                              |                                  | Canonical Events vs. Audit. |
+----+------------------------------+----------------------------------+-----------------------------+
| 5  | AI Confirmation Authority    | Universal clinician review queue | BIFURCATED: Patient Confirms|
|    |                              | for all AI extractions.          | intake observations; Doctor |
|    |                              |                                  | Reviews clinical synthesis. |
+----+------------------------------+----------------------------------+-----------------------------+
| 6  | Medication Boundary          | Generalized medication event     | FORMALIZED: MedicationPlan  |
|    |                              | modeling.                        | is clinician-authored only; |
|    |                              |                                  | AI has zero dosing power.   |
+----+------------------------------+----------------------------------+-----------------------------+
| 7  | Migration Phasing & Timeline | Outlined calendar-based 8-week   | RESTRUCTURED: Milestone     |
|    |                              | migration timeline.              | gates with verifiable       |
|    |                              |                                  | technical exit criteria.    |
+----+------------------------------+----------------------------------+-----------------------------+
```

---

## 2. Frozen Architectural Decisions

The technology stack is **frozen**. These decisions represent immutable project baseline specifications:

```
+----------------------------------------------------------------------------------------------------+
|                                      FROZEN TECHNOLOGY STACK                                       |
+------------------------------+------------------------------------+--------------------------------+
| Architectural Subsystem      | Frozen Technology Selection        | Architectural Specification    |
+------------------------------+------------------------------------+--------------------------------+
| Universal Mobile Runtime     | React Native + Expo                | Single binary cross-platform.  |
| Mobile Navigation            | Expo Router                        | File-based typed routing.      |
| Mobile Client State          | Zustand                            | Lightweight immutable stores.  |
| Server State & Caching       | TanStack Query (React Query)       | Async query invalidation & sync|
| Mobile Form Handling         | React Hook Form + Zod              | Schema-driven type validation. |
| Local Encrypted Mobile DB    | Expo SQLite + SQLCipher            | Offline-first AES-256 store.   |
| Mobile Local ORM             | Drizzle ORM                        | Type-safe relational mapping.  |
+------------------------------+------------------------------------+--------------------------------+
| Shared Backend Runtime       | FastAPI (Python 3.10+)             | High-throughput ASGI core.     |
| Validation & Serialization   | Pydantic v2                        | Schema contracts & DTOs.       |
| Backend ORM & Persistence    | SQLAlchemy 2.0 + Alembic           | Async relational mapping.      |
| Production Database          | PostgreSQL                         | Relational multi-tenant core.  |
| Database Extensions          | TimescaleDB, PostGIS, pgvector     | Enabled where justified.       |
| Distributed Cache & Broker   | Redis                              | In-memory caching & task queue.|
| Object / Document Storage    | S3-Compatible Object Storage       | AWS S3, MinIO, or Ceph.        |
+------------------------------+------------------------------------+--------------------------------+
| Identity & Access Management | Keycloak (OAuth2 / OIDC / JWT)     | Centralized SSO & IdP service. |
| Authorization Engine         | RBAC + Relationship Permissions    | Policy enforcement + PG RLS.   |
| AI / Scientific Computing    | Python + PyTorch / scikit-learn /  | Native statistical and ML      |
|                              | XGBoost / LightGBM                 | algorithms as needed.          |
| Cloud Infrastructure Target  | Cloud-Agnostic Container Topology  | Docker / Kubernetes deployment.|
+------------------------------+------------------------------------+--------------------------------+
```

---

## 3. Final Phase-1 Application Boundary

Phase 1 encompasses four tightly coupled components sharing one backend:

```
                                    PHASE 1 ARCHITECTURE
                                   
      ┌──────────────────────────────────────────────┐    ┌──────────────────────────────┐
      │ APPLICATION 1: Universal Mobile Application  │    │ APPLICATION 2: Admin Console │
      │           (React Native + Expo)              │    │      (Web SPA: Next.js)      │
      │                                              │    │                              │
      │  +------------------+  +------------------+  │    │  - Tenant & Org Governance   │
      │  | THALI Experience |  | P.L.A.T.E. Mobile|  │    │  - User & Role Provisioning  │
      │  | (Patient / CG)   |  | (Doctor, Nurse,  |  │    │  - Consent & Audit Logs      │
      │  | - Self Logging   |  |  Coord, Dietitian|  │    │  - Device & Channel Health   │
      │  | - Plate Confirm  |  |  Field Worker)   |  │    │  - AI Staging & Governance   │
      │  | - Adherence/Meds |  | - Mobile Consult │  │    └──────────────┬───────────────┘
      │  +------------------+  +------------------+  │                   │
      └───────────────────────┬──────────────────────┘                   │
                              │ HTTPS / WSS                              │ HTTPS / WSS
                              ▼                                          ▼
      ┌──────────────────────────────────────────────────────────────────────────────────┐
      │ SHARED FASTAPI BACKEND (Python 3.10+ / PostgreSQL / Redis / Keycloak / S3)       │
      └───────────────────────────────────────▲──────────────────────────────────────────┘
                                              │ HTTPS (HMAC-SHA256 Verified)
      ┌───────────────────────────────────────┴──────────────────────────────────────────┐
      │ CHANNEL: WhatsApp Business Cloud API (First-Class Telemetry Gateway)             │
      └──────────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1 Core Tenets:
1. **Universal Mobile Application**: Single mobile binary dynamically rendering the **THALI** interface for Patients/Caregivers and the **P.L.A.T.E. Mobile** interface for Doctors, Nurses, Coordinators, Dietitians, and Field Workers based on active Keycloak role context.
2. **Mobile-First Doctor Experience**: The clinical P.L.A.T.E. consultation readiness view, glycemic corridor charts, 2-page lab PDF preview, and intake review queues are delivered **first on mobile devices**.
3. **Admin Web Console**: Desktop browser workstation dedicated strictly to organizational setup, facility configuration, user RBAC provisioning, consent auditing, and channel health monitoring.
4. **WhatsApp Channel**: First-class asynchronous ingestion channel feeding the exact same backend and canonical event pipeline.

---

## 4. Final Phase-2 Boundary

```
+----------------------------------------------------------------------------------------------------+
|                                    PHASE 2 EXPANSION BOUNDARY                                      |
+----------------------------------------------------------------------------------------------------+
| OPTIONAL COMPONENT: P.L.A.T.E. Clinical Web Workstation                                            |
|                                                                                                    |
| - Large-screen desktop OPD clinical workstation (Next.js / React).                                 |
| - Optimized for multi-monitor outpatient consultation suites and high-throughput ward rounds.      |
| - Consumes the identical v2 REST/WebSocket APIs as the Universal Mobile Application.               |
| - Decoupled completely from the Phase 1 critical delivery path.                                    |
+----------------------------------------------------------------------------------------------------+
```

* **Architectural Invariant**: The P.L.A.T.E. Web Workstation is an optional, secondary delivery channel. No Phase 1 clinical workflow or database dependency shall be blocked pending web workstation readiness.

---

## 5. Domain Entities vs. Canonical Events Boundary

The system maintains a strict separation between **Mutable Domain State**, **Immutable Canonical Events**, **Audit Records**, and **System Telemetry**:

```
+----------------------------------------------------------------------------------------------------+
|                                  STATE & EVENT TAXONOMY MATRIX                                     |
+-----------------------------+-----------------------------+----------------------------------------+
| Classification              | Architectural Semantics     | Concrete Concrete System Entities      |
+-----------------------------+-----------------------------+----------------------------------------+
| 1. Domain Entities          | Relational, mutable,        | - User                                 |
|    (Current State)          | query-optimized state.      | - Organization                         |
|                             | Represents the current      | - Facility                             |
|                             | operational truth.          | - Patient                              |
|                             |                             | - CaregiverRelationship                |
|                             |                             | - CareTeamMembership                   |
|                             |                             | - ConsentGrant                         |
|                             |                             | - CarePlan                             |
|                             |                             | - MedicationPlan (Clinician-authored)  |
+-----------------------------+-----------------------------+----------------------------------------+
| 2. Canonical Domain Events  | Immutable, append-only,     | - observation.glucose                  |
|    (Historical Stream)      | timestamped clinical,       | - intake.meal                          |
|                             | behavioral, or intake       | - medication.administration            |
|                             | transactions. Emitted when  | - document.ingestion                   |
|                             | state changes or tele-      | - clinical.appointment                 |
|                             | metry arrives.              | - workflow.care_task                   |
|                             |                             | - communication.inbound                |
+-----------------------------+-----------------------------+----------------------------------------+
| 3. Audit Events             | Immutable compliance        | - auth.login / logout / token_refresh  |
|    (Security & Access)      | ledger recording who        | - rbac.role_assigned / revoked         |
|                             | accessed or mutated what    | - consent.granted / revoked            |
|                             | record, when, and from where| - record.viewed / exported / printed   |
|                             |                             | - ai_draft.reviewed / approved / edit  |
+-----------------------------+-----------------------------+----------------------------------------+
| 4. System / Channel         | Operational diagnostic      | - gateway.webhook_received             |
|    Telemetry                | logs capturing HTTP latency,| - gateway.hmac_validated / failed      |
|                             | gateway errors, and task    | - worker.task_started / completed      |
|                             | queue metrics.              | - sync.batch_uploaded / acknowledged   |
+-----------------------------+-----------------------------+----------------------------------------+
```

### Relational Schema Evolution (PostgreSQL)

```
  DOMAIN STATE TABLES                     CANONICAL EVENT BUS                   COMPLIANCE & TELEMETRY
  
  ┌───────────────────────┐               ┌───────────────────────┐             ┌───────────────────────┐
  │ users                 │               │ canonical_events      │             │ immutable_audit_log   │
  │ organizations         │  State        │ - event_id (UUIDv7)   │             │ - audit_id (UUID)     │
  │ facilities            │  Changes      │ - patient_id          │             │ - actor_id            │
  │ patients              │ ────────────► │ - event_type          │             │ - action              │
  │ caregiver_rel         │  Emit         │ - observed_at         │             │ - resource_id         │
  │ care_plans            │  Events       │ - payload (JSONB)     │             │ - timestamp           │
  │ medication_plans      │               │ - provenance          │             └───────────────────────┘
  │ consent_grants        │               └───────────────────────┘             ┌───────────────────────┐
  └───────────────────────┘                           ▲                         │ gateway_telemetry     │
              ▲                                       │ Ingests Observations    │ - request_id          │
              │ Materialized                          │ via Gateway             │ - hmac_status         │
              │ Projections                           │                         │ - latency_ms          │
              └───────────────────────────────────────┴──────────────────────── └───────────────────────┘
```

---

## 6. Bifurcated AI Confirmation Authority Model

The universal AI staging queue designed in Gate 01 has been corrected. AI confirmation authority is explicitly separated into two distinct pipelines:

```
+----------------------------------------------------------------------------------------------------+
|                                    BIFURCATED CONFIRMATION FLOWS                                   |
+----------------------------------------------------------------------------------------------------+

PATH A: PATIENT OBSERVATION CONFIRMATION (Self-Management / Intake)
----------------------------------------------------------------------------------------------------
Unstructured Inbound (WhatsApp text / photo / voice / mobile input)
         │
         ▼
Deterministic Regex Parser (app/core/parse.py) -> AI Extractor (app/core/intake_ai.py)
         │
         ▼
Draft Observation Candidate (e.g. "Roti, Dal · Medium 220ml katori")
         │
         ▼
PATIENT CONFIRMATION LOOP (Interactive WhatsApp template / THALI Mobile Sheet)
         │
         ├─► Patient Replies "YES" / Confirms     ──► Inscribe to Canonical Event Store
         ├─► Patient Adjusts "correct l" (Large)  ──► Update Portion -> Inscribe Canonical Event
         └─► Patient Rejects / Inactivity         ──► Expire Draft Candidate (Audit logged)

*Clinicians are NOT burdened with reviewing daily patient meal extractions.*


PATH B: CLINICIAN REVIEW & SYNTHESIS APPROVAL (Clinical Decision Support)
----------------------------------------------------------------------------------------------------
Verified Canonical Observations (readings, confirmed meals)
         │
         ▼
Deterministic Analytics Engine (app/core/metrics.py: TIR, FPG, Slots, CVI, r)
         │
         ▼
Evidence Package Compiler (app/report/context.py & charts.py)
         │
         ▼
AI Pattern Synthesis & Consultation Digest (Google Gemini / LLM Client)
         │
         ▼
CLINICIAN REVIEW QUEUE (P.L.A.T.E. Mobile Consultation View)
         │
         ├─► Clinician Approves           ──► Attach to Official Consultation Record & PDF
         ├─► Clinician Edits & Approves   ──► Save Modified Summary & Record Clinical Diff
         └─► Clinician Rejects            ──► Discard Draft; Retain Pure Deterministic Context
```

### Medication Safety Invariants:
1. **Clinician Authority**: All `MedicationPlan` records originate solely from licensed clinicians.
2. **Zero AI Dosing / Prescribing**: AI models are programmatically barred from suggesting, calculating, or altering medication doses, timings, or titrations.
3. **Patient Administration Logging**: Patients log adherence check-ins (`MedicationAdministrationEvent`) against clinician instructions.
4. **Deterministic Comparison**: Adherence analytics compare observed administrations against prescribed orders deterministically without inventing scheduling rules.

---

## 7. Final Migration Principles (Gate → Verify → Gate)

The 8-week illustrative timeline is discarded. Migration progresses strictly across **milestone gates with verifiable technical exit criteria**:

```
+----------------------------------------------------------------------------------------------------+
|                                  TECHNICAL MILESTONE GATES                                         |
+------------------------+------------------------------------+--------------------------------------+
| Milestone Gate         | Primary Engineering Deliverables   | Technical Exit Criteria              |
+------------------------+------------------------------------+--------------------------------------+
| **GATE 00** (Complete) | Codebase reconnaissance & baseline.| 57 tests passing; audit document.    |
+------------------------+------------------------------------+--------------------------------------+
| **GATE 01** (Complete) | Architecture reconciliation.       | Target reconciliation matrix.        |
+------------------------+------------------------------------+--------------------------------------+
| **GATE 01.1** (Current)| Frozen decision & boundary fixes.  | Corrected baseline document.         |
+------------------------+------------------------------------+--------------------------------------+
| **GATE 02**            | Domain entities, database schemas, | SQLAlchemy models, Alembic scripts,  |
| (Domain Scaffolding)   | Keycloak auth contracts, and OpenAPI| passing unit test fixtures.          |
+------------------------+------------------------------------+--------------------------------------+
| **GATE 03**            | Shared backend core, HMAC WhatsApp | Dual-write facade active; all 57     |
| (Backend & Security)   | gateway, and Canonical Event Bus.  | baseline tests passing in green.     |
+------------------------+------------------------------------+--------------------------------------+
| **GATE 04**            | Universal React Native mobile app  | Mobile role switching operational;   |
| (Mobile & Admin App)   | (THALI & P.L.A.T.E.) & Admin Web.  | local SQLCipher sync verified.       |
+------------------------+------------------------------------+--------------------------------------+
| **GATE 05**            | End-to-end integration, performance| Live Meta WhatsApp end-to-end audit; |
| (Verification & Cutover| load testing, and legacy cutover.  | zero unauthenticated endpoints.      |
+------------------------+------------------------------------+--------------------------------------+
| **GATE 06**            | Production deployment and legacy   | SQLite archived; static dashboard    |
| (Decommissioning)      | asset decommissioning.             | removed; production monitoring live. |
+------------------------+------------------------------------+--------------------------------------+
```

---

## 8. Remaining Genuine Unknowns

Only genuine technical unknowns remain; all architecture-indecision items have been resolved:

1. **SMS / OTP Gateway Provider**: Which licensed Indian SMS gateway (e.g., Gupshup, Exotel, Twilio India) will handle DPDPA-compliant patient verification and consent grants?
2. **Offline Image Caching Quota**: What is the target disk cache limit for local meal photos on mobile devices running SQLCipher before enforcing local thumbnail eviction?
3. **Low-Bandwidth Telemetry Target**: What is the maximum acceptable payload size for batch synchronization over 2G/3G networks in rural primary health centers?

---

## 9. Gate 02 Prerequisites

The following checklist must be satisfied to initiate **GATE 02 (Domain Model Scaffolding & Database Migration Engine)**:
- [x] GATE 00 Reconnaissance Audit verified and locked.
- [x] GATE 01 Architecture Reconciliation completed.
- [x] GATE 01.1 Corrections Pass accepted and frozen decisions codified.
- [ ] Specification of SQLAlchemy 2.0 multi-tenant declarative models.
- [ ] Alembic migration environment scaffolding targeting PostgreSQL.
- [ ] Keycloak client profile definition and JWT role-claim mapping specification.
- [ ] OpenAPI 3.1 contract generation for Phase 1 endpoints (`/api/v2/`).

---

```
================================================================================
GATE 01.1 STATUS: READY FOR GATE 02
================================================================================
All architectural corrections have been applied. The frozen technology decisions
(React Native + Expo, Keycloak, S3, PostgreSQL, Drizzle/SQLCipher, FastAPI) are
firmly anchored. Phase 1 is established as mobile-first (Universal Mobile App +
Admin Web + WhatsApp + Shared Backend), P.L.A.T.E. Clinical Web is moved to
Phase 2, domain entities are decoupled from canonical events, and the AI
confirmation authority model is properly bifurcated. The program is ready for
Gate 02 implementation planning.
================================================================================
```
