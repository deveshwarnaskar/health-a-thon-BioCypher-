# GATE SEQUENCE RECONCILIATION
## THALI × P.L.A.T.E. Production Program

**Document ID**: `GATE-SEQUENCE-RECONCILIATION`  
**Classification**: Architectural Reconciliation & Gate Sequence Governance (Read-Only Analysis)  
**Execution Date**: 2026-09-15  
**Current Working Branch**: `feature/gate-06-api-security`  
**Canonical Predecessor (Gate 05)**: `5503ad0d4f986fea5ebd88b3db988b0c8b4b4cde` (`gate-05-infrastructure-adapters-complete`)  
**Current Gate 06 Checkpoint**: `c6c7614` (`gate-06-api-security-complete`)  
**Target Repository**: `/Users/subhamdas/Documents/health-a-thon-BioCypher--master`  
**Author**: Antigravity Architecture & Security Governance  

---

## 1. Executive Summary

This document establishes the authoritative architectural reconciliation of the **THALI × P.L.A.T.E. Production Program** gate progression sequence. It resolves the structural tension between the original ten-phase roadmap established in **Gate 02A**, the scope executed in **Gate 06**, the findings of the **Gate 06 Completion Gap Analysis**, and the locked status of **Gate 07**.

### 1.1 Architectural Reconciliation Mandate
In strict compliance with governance rules:
- **No source code has been modified, created, moved, or deleted.**
- **No tests have been modified, added, or deleted.**
- **No Git commits or tags have been created, amended, moved, or deleted.**
- **No database migrations have been executed.**
- **The full test suite remains 100% green: 226 passed, 0 failures (57 Gate 00 baseline + 48 Gate 03 domain/config + 49 Gate 04 application/architecture + 55 Gate 05 infrastructure + 17 Gate 06 security).**

### 1.2 The Core Problem
The original Gate 06 prompt envisioned a massive "API + Security Boundary" that bundled:
1. Low-level cryptographic primitives (HMAC-SHA256, JWT verification, webhook signature verification).
2. HTTP transport, routing, and dependency injection (FastAPI application factory, `/api/v2` routes, request/response DTOs).
3. End-to-end multi-tenant request context binding (JWT $\rightarrow$ `AuthenticatedContext` $\rightarrow$ `tenant_id` $\rightarrow$ `UnitOfWork` $\rightarrow$ PostgreSQL Row Level Security `set_config`).
4. Role-based access control (RBAC) policy enforcement.
5. Fine-grained relationship-aware authorization (caregiver $\leftrightarrow$ patient access, clinician facility scoping).
6. Patient self-access identity mapping (Keycloak identity/phone claim $\rightarrow$ patient persona).
7. Operational security infrastructure (webhook replay protection, idempotency store, rate limiting, audit event logging).

### 1.3 What Gate 06 Actually Accomplished
Gate 06 delivered genuine, production-grade **Cryptographic Security Primitives** under commit `c6c7614`:
- Pure standard-library JWT HS256 cryptographic verification (`hmac`, `hashlib`, `base64`, `secrets`).
- Byte-exact, raw-body Meta WhatsApp `X-Hub-Signature-256` verification.
- Meta WhatsApp `hub.challenge` verify-token handshake.
- A neutral, PHI-minimal inbound event envelope (`WhatsAppInboundEnvelope`).
- Constant-time cryptographic comparison (`hmac.compare_digest`) throughout.
- 17 exhaustive regression tests covering valid payloads, tampered bodies, wrong secrets, unsupported algorithms (`alg=none`), malformed tokens, and empty keys.

### 1.4 The Architectural Gap
Gate 06 did **not** implement the HTTP transport boundary, route registration, dependency injection, DTO mapping, RBAC policies, HTTP error handlers, rate limiting, idempotency, or audit logging. 

Crucially, the gap analysis revealed that **two critical security requirements cannot be implemented within the HTTP boundary today because their underlying domain ports, persistence models, and database schemas do not exist**:
1. **Per-Patient Caregiver Relationship Authorization**: In Gate 03, `CaregiverRelationship` was defined as a pure domain entity. However, no `CaregiverRelationshipRepository` port was created in Gate 04, no relational model was created in Gate 05, no database table was migrated in Alembic, and no RLS policy was established.
2. **Patient Self-Access Identity Bridge**: The system possesses no `IdentityPatientMappingPort` or contract linking an authenticated Keycloak user identity (`sub`) or verified phone claim to a domain `PatientProfile`.

If an HTTP boundary were forced to implement these features without their underlying contracts, it would be forced to adopt catastrophic security shortcuts:
- *Doctor role $\rightarrow$ access any patient* (Universal access violation).
- *Caregiver role $\rightarrow$ access any patient* (Universal access violation).
- *Patient role $\rightarrow$ trust unverified `patient_id` in route parameter* (Insecure Direct Object Reference / IDOR).

### 1.5 The Reconciliation Decision
1. **Gate 06** is formally classified and closed as a **Cryptographic Security Primitives Milestone** (`c6c7614`, tag `gate-06-api-security-complete`). Its Git history and tag remain untouched.
2. The remaining work is unbundled according to architectural dependencies into three focused, verifiable gates:
   - **Gate 07: HTTP Transport, Dependency Injection & Security Boundary** (FastAPI app factory, `/api/v2` routes, DI, `AuthenticatedContext`, JWT $\rightarrow$ RLS binding, coarse RBAC, safe error handling, security headers, health checks). Caregiver and patient self-access remain strictly **deny-by-default**.
   - **Gate 08: Relational Identity & Clinical Authorization** (`CaregiverRelationshipRepository` port, database schema, Alembic migration, RLS policy, `IdentityPatientMappingPort`, caregiver authorization, patient self-access).
   - **Gate 09: Operational Resiliency, Idempotency & Channel Orchestration** (`IdempotencyStore` port + adapter, replay protection, rate limiting, `AuditStore` port + adapter, webhook asynchronous dispatch).

---

## 2. Current Frozen Checkpoints

The repository maintains an unbroken, verified Git and test lineage:

```
0d4613c (tag: baseline-gate-00)
   │    [57 legacy tests passing — pristine Aahaar prototype]
   ▼
6bd6f33 (tag: gate-02b-scaffolding-complete)
   │    [Repository layout, clean architecture directories, import shims]
   ▼
d38373e (tag: gate-03-domain-extraction-complete)
   │    [Pure domain entities, value objects, clinical invariants, config]
   │    [105 tests passing = 57 legacy + 48 domain/config]
   ▼
bb04699 (tag: gate-04-application-layer-complete)
   │    [Application use cases, outbound ports, DTO boundaries, UoW contract]
   │    [154 tests passing = 105 predecessor + 49 application/architecture]
   ▼
5503ad0 (tag: gate-05-infrastructure-adapters-complete)  <-- CANONICAL APPROVED PREDECESSOR
   │    [PostgreSQL persistence, SQLAlchemy 2.x, Alembic, PostgreSQL RLS, Redis, S3]
   │    [209 tests passing = 154 predecessor + 52 infra unit + 3 live integration]
   ▼
c6c7614 (tag: gate-06-api-security-complete, branch: feature/gate-06-api-security)
        [Cryptographic primitives: JWT HS256, WhatsApp HMAC, handshake, neutral envelope]
        [226 tests passing = 209 predecessor + 17 security primitive tests]
        [Status: Cryptographic primitives complete; HTTP/Authz scope incomplete]
```

### Table 2.1: Checkpoint Verification Matrix

| Gate | Commit SHA | Annotated Git Tag | Test Suite Count | Status | Notes |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **Gate 00** | `0d4613c` | `baseline-gate-00` | 57 | **APPROVED** | Baseline Aahaar prototype frozen |
| **Gate 02B** | `6bd6f33` | `gate-02b-scaffolding-complete` | 57 | **APPROVED** | Monorepo layout scaffolded |
| **Gate 03** | `d38373e` | `gate-03-domain-extraction-complete` | 105 | **APPROVED** | Domain models & invariants |
| **Gate 04** | `bb04699` | `gate-04-application-layer-complete` | 154 | **APPROVED** | Application orchestration & ports |
| **Gate 05** | `5503ad0` | `gate-05-infrastructure-adapters-complete` | 209 | **APPROVED** | Persistence & PostgreSQL RLS |
| **Gate 06** | `c6c7614` | `gate-06-api-security-complete` | 226 | **PARTIAL** | Cryptographic primitives only; gap analysis completed; final checkpoint not approved |
| **Gate 07** | *None* | *None* | — | **LOCKED** | Implementation not started |

---

## 3. Original Gate 02A Sequence

The master blueprint [GATE_02A_REPOSITORY_MIGRATION_MAP.md](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/GATE_02A_REPOSITORY_MIGRATION_MAP.md#L815-L868) defined a ten-phase migration order. The following table extracts each original phase, evaluates its expected outputs against current implementation, and identifies whether the existing architecture satisfies it.

### Table 3.1: Ten-Phase Migration Reconciliation

| Phase | Original Purpose | Expected Outputs | Current Implementation Status | Mapped Gate | Architecture Satisfied? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1: Git Baseline & Skeleton** | Initialize Git, create directory layout, establish package shims. | Initialized Git repo, `.gitignore`, directory tree (`backend/`, `apps/`, `config/`), backward-compatible import shims in `app/`. | **COMPLETE** | Gate 02B (`6bd6f33`) | **YES**. Baseline preserved; 57/57 tests green. |
| **Phase 2: Config & Pure Domain** | Introduce Pydantic v2 settings, Value Objects (Glucose, Katori, Phone). | `config/settings.py` (`BaseSettings`), Value Objects (`GlucoseValue`, `KatoriVolume`, `PhoneNumber`, `UHID`, `TimeWindow`), Domain Entities, clinical invariants. | **COMPLETE** | Gate 03 (`d38373e`) | **YES**. Domain layer is pure Python (stdlib only). |
| **Phase 3: Application Layer & Ports** | Implement Commands, Queries, and Port interfaces. Wrap core calculation routines. | Application use-case services (12 handlers), Outbound Port interfaces (`UnitOfWork`, repositories, `Clock`, `IdGenerator`, `DomainEventPublisher`), DTO boundaries. | **COMPLETE** | Gate 04 (`bb04699`) | **YES**. Strict dependency inversion enforced. |
| **Phase 4: Compatibility Bridge Layer** | Deploy `LegacyStoreAdapter` and legacy v1 router. Decouple `main.py`. | `backend/compatibility/legacy_v1_router.py`, `legacy_store_adapter.py`, mapping legacy integer `patient_id` to UUID, zero direct dependencies on legacy `main.py`. | **PARTIALLY DEFERRED** | Deferred to HTTP application assembly | **PARTIAL**. 57 baseline tests run green via legacy `app/` modules. Formal `legacy_v1_router.py` awaits FastAPI app factory. |
| **Phase 5: Infrastructure Layer** | Deploy SQLAlchemy 2.0 models, Alembic migrations, TimescaleDB event store. | SQLAlchemy 2.0 ORM models, Alembic migrations, concrete repositories, `SqlAlchemyUnitOfWork` with transaction-local RLS, Redis cache, S3 storage, Keycloak validator. | **COMPLETE** | Gate 05 (`5503ad0`) | **YES**. Relational schema and PostgreSQL RLS fully operational. |
| **Phase 6: Enterprise API v2 & Security** | Deploy `/api/v2` endpoints, Keycloak OIDC, HMAC-SHA256 webhook verification. | FastAPI app factory (`create_app`), `/api/v2` routes, JWT verification, PostgreSQL RLS session context binding, HMAC webhook verifier, RBAC middleware, rate limiting. | **SPLIT / PARTIAL** | Gate 06 (`c6c7614`) & Gate 07 (Proposed) | **NO (PARTIAL)**. Cryptographic verification implemented in Gate 06; HTTP routing and authorization missing. |
| **Phase 7: Mobile App Scaffolding** | Initialize React Native + Expo monorepo under `apps/mobile`. Configure Drizzle ORM. | Mobile app route tree, Zustand client state, TanStack Query hooks, clinical widgets, offline SQLite + SQLCipher schema. | **NOT STARTED** | Future Gate (Gate 10) | **PENDING**. Blocked on stable HTTP API v2. |
| **Phase 8: Admin Web Scaffolding** | Initialize Admin Web React SPA under `apps/admin-web`. | Facility, tenant, and user management UI, Admin REST client, mock API integration. | **NOT STARTED** | Future Gate (Gate 10) | **PENDING**. Blocked on stable HTTP API v2. |
| **Phase 9: Dual-Run & Data Migration** | Execute `migrate_sqlite_to_postgres.py`; verify parity across databases. | One-way data migrator from `aahaar.db` to PostgreSQL, dual-run comparison suite, parity validation. | **NOT STARTED** | Future Gate (Gate 11) | **PENDING**. Blocked on completed backend and interfaces. |
| **Phase 10: Legacy Cutover** | Decommission legacy static files and SQLite database; seal production v2. | Removal of legacy `app/` monolithic scripts, retirement of SQLite, production hardening. | **NOT STARTED** | Future Gate (Gate 12) | **PENDING**. Final production release. |

---

## 4. Original Gate 06 Scope

The "Original Gate 06 Contract" comprised 36 explicit architectural and security requirements. The following matrix enumerates every requirement, classifies its functional concern, and establishes its structural category:
- **PRIMITIVE**: Self-contained mathematical, cryptographic, or algorithmic logic.
- **BOUNDARY**: Transport-level adapter, serializer, envelope, or protocol mapper.
- **INTEGRATION**: Cross-component wiring connecting distinct architectural subsystems.
- **CONTRACT**: Formal interface, port definition, or domain specification.
- **INFRASTRUCTURE**: External system client, database adapter, or storage driver.

### Table 4.1: Original Gate 06 Requirements Classification

| # | Requirement | Functional Concern | Structural Category | Description |
| :---: | :--- | :--- | :--- | :--- |
| **1** | Valid HS256 JWT acceptance | Cryptographic primitive | **PRIMITIVE** | Constant-time HMAC-SHA256 signature verification over valid tokens. |
| **2** | Tampered JWT payload rejection | Cryptographic primitive | **PRIMITIVE** | Rejection of tokens where payload or header bytes have been modified. |
| **3** | Wrong secret JWT rejection | Cryptographic primitive | **PRIMITIVE** | Rejection of tokens signed with an invalid secret key. |
| **4** | Unsupported `alg=none` rejection | Cryptographic primitive | **PRIMITIVE** | Strict allow-list enforcement rejecting unsigned or alternate algorithm tokens. |
| **5** | Malformed JWT structure rejection | Cryptographic primitive | **PRIMITIVE** | Rejection of tokens not containing exactly three base64url segments. |
| **6** | Malformed base64 / empty secret | Cryptographic primitive | **PRIMITIVE** | Rejection of un-padded/corrupted base64 and refusal of empty secret keys. |
| **7** | Deterministic signature input serialization | Cryptographic primitive | **PRIMITIVE** | Byte-exact reconstruction of `b64(header).b64(payload)` input. |
| **8** | Valid `X-Hub-Signature-256` acceptance | Webhook security | **PRIMITIVE** | Constant-time HMAC-SHA256 verification of Meta WhatsApp payload signatures. |
| **9** | Tampered webhook body rejection | Webhook security | **PRIMITIVE** | Immediate rejection if raw payload bytes deviate from signature. |
| **10** | Wrong secret webhook rejection | Webhook security | **PRIMITIVE** | Rejection of webhooks signed with mismatched app secrets. |
| **11** | Missing webhook header rejection | Webhook security | **PRIMITIVE** | HTTP 401/403 rejection when `X-Hub-Signature-256` header is omitted. |
| **12** | Empty webhook header rejection | Webhook security | **PRIMITIVE** | Rejection when signature header contains empty or whitespace value. |
| **13** | Wrong prefix webhook rejection | Webhook security | **PRIMITIVE** | Rejection of signatures missing the mandatory `sha256=` prefix. |
| **14** | Valid verify-token challenge echo | Webhook security / Auth | **PRIMITIVE** | Echoing `hub.challenge` on valid GET handshake tokens. |
| **15** | Mismatched verify-token rejection | Webhook security / Auth | **PRIMITIVE** | Rejection of GET handshake requests with incorrect verify tokens. |
| **16** | Unsupported handshake mode rejection | Webhook security / Auth | **PRIMITIVE** | Rejection of GET handshake requests where `hub.mode != 'subscribe'`. |
| **17** | Inbound envelope PHI minimization | Webhook security | **BOUNDARY** | Normalizing raw WhatsApp payloads to `<id, phone, event, time>` only. |
| **18** | OpenAPI / Request schema boundary | API DTO | **BOUNDARY** | Pydantic v2 DTOs validating inbound request bodies and sanitizing responses. |
| **19** | Security error boundary | Error handling | **BOUNDARY** | Uniform JSON error responses preventing stack trace and internal leaks. |
| **20** | RBAC authorization policy | Authorization | **CONTRACT / INTEGRATION** | Role-to-operation permission evaluation (`can_author_medication`, etc.). |
| **21** | Per-patient caregiver authorization | Authorization | **CONTRACT** | Proving active, non-revoked caregiver proxy relationship for target patient. |
| **22** | Tenant isolation via PostgreSQL RLS | Tenant isolation | **INTEGRATION** | Authoritative propagation of JWT `tenant_id` into UoW transaction RLS. |
| **23** | Patient self-access identity bridge | Authentication / Authz | **CONTRACT** | Cryptographic mapping connecting JWT `sub`/phone to a domain `patient_id`. |
| **24** | Caregiver access to unlinked patient deny | Authorization | **CONTRACT / INTEGRATION** | Fail-closed denial when caregiver has no relationship record for patient. |
| **25** | Clinician cross-facility access deny | Authorization | **CONTRACT / INTEGRATION** | Enforcement of facility boundary rules for assigned clinical personnel. |
| **26** | Authorized relationship allow | Authorization | **CONTRACT / INTEGRATION** | Granting access when relationship, role, and tenant checks all pass. |
| **27** | Webhook replay protection | Webhook security / Idempotency | **CONTRACT / INFRASTRUCTURE** | Cache/DB check preventing reprocessing of previously seen message IDs. |
| **28** | Webhook deduplication store | Idempotency | **CONTRACT / INFRASTRUCTURE** | Store-first deduplication mechanism for inbound channel webhooks. |
| **29** | Rate limiting per tenant/user/IP | Rate limiting | **CONTRACT / INFRASTRUCTURE** | Sliding window / token bucket rate limiting on HTTP endpoints. |
| **30** | Audit event logging | Audit | **CONTRACT / INFRASTRUCTURE** | Immutable append-only audit trail capturing actor, tenant, op, and target. |
| **31** | PHI redaction in logs | Observability | **INFRASTRUCTURE** | Automatic masking of phone numbers, names, and clinical values in logs. |
| **32** | Channel envelope PHI exclusion | API DTO / Webhook | **BOUNDARY** | Enforcing zero clinical observations or carb values in channel envelopes. |
| **33** | HTTP transport / Route wiring | HTTP transport | **BOUNDARY** | FastAPI app factory (`create_app`), `/api/v2` routers, path handlers. |
| **34** | OpenAPI exposure policy | Security middleware | **BOUNDARY** | Environment-gated exposure of `/docs` and `/openapi.json`. |
| **35** | HTTP Dependency Injection boundary | HTTP transport | **BOUNDARY** | FastAPI `Depends()` graph providing UoW, auth context, and use cases. |
| **36** | 500 stack trace suppression & headers | Security middleware | **BOUNDARY** | Security headers (HSTS, CSP) and safe HTTP 500 exception handlers. |

---

## 5. Actual Gate 06 Implementation

Under commit `c6c7614`, Gate 06 established the cryptographic foundation of the API layer without taking on external framework dependencies.

### 5.1 Delivered Components
1. **JWT HS256 Verifier** (`backend/interfaces/http/v2/security/jwt.py`):
   - Decodes exactly three base64url segments; rejects any malformed structure.
   - Enforces an algorithm allow-list (`HS256` only); explicitly rejects `alg=none`.
   - Computes canonical `HMAC-SHA256(secret, b64(header).b64(payload))`.
   - Executes constant-time comparison via `hmac.compare_digest`.
   - Returns a frozen, typed `Hs256Result` or raises `JwtSignatureError`.
2. **Role Token Normalization** (`backend/interfaces/http/v2/security/roles.py`):
   - Normalizes realm role strings into canonical `CareTeamRole` tokens (`DOCTOR`, `NURSE`, `CARE_COORDINATOR`, `DIETITIAN`, `FIELD_WORKER`).
3. **WhatsApp Webhook Signature Verifier** (`backend/interfaces/http/v2/webhooks/whatsapp/signature.py`):
   - Verifies `X-Hub-Signature-256` over the exact **raw request body bytes**.
   - Requires the mandatory `sha256=` prefix.
   - Performs constant-time comparison using `hmac.compare_digest`.
   - Raises typed `WebhookSignatureError` on missing, malformed, or mismatched signatures.
4. **WhatsApp Verify-Token Handshake** (`backend/interfaces/http/v2/webhooks/whatsapp/verify_token.py`):
   - Implements the Meta GET verification handshake.
   - Validates `hub.mode == 'subscribe'` and verifies the challenge token in constant time.
   - Echoes `hub.challenge` or raises `VerifyTokenError`.
5. **PHI-Minimal Inbound Envelope** (`backend/interfaces/http/v2/webhooks/whatsapp/envelope.py`):
   - Normalizes provider payloads into `WhatsAppInboundEnvelope`.
   - Contains strictly primitive fields: `message_id`, `source_phone`, `event_type`, `timestamp`.
   - Carries **zero PHI**, zero clinical metrics, and zero domain entity imports.
6. **Exhaustive Cryptographic Test Suite** (17 tests, 100% pass):
   - `tests/security/test_jwt_hs256_signature.py` (7 tests).
   - `tests/security/test_whatsapp_webhook.py` (10 tests).

### 5.2 What Gate 06 Did NOT Implement
- **No FastAPI Application**: `backend/interfaces/http/app.py` does not exist.
- **No Route Handlers**: No `/api/v2/*` routes are registered or wired.
- **No HTTP Dependency Injection**: No FastAPI `Depends` providers for use cases or UoW.
- **No Request/Response DTOs**: Inbound HTTP request parsing and validation are absent.
- **No Authenticated Context**: No principal data structure representing the authenticated actor.
- **No HTTP Authorization**: No middleware or dependency evaluating role permissions.
- **No Tenant Context Binding at HTTP Boundary**: The JWT `tenant_id` is never passed to `SqlAlchemyUnitOfWork`.
- **No Rate Limiting, Idempotency, or Audit Stores**: Operational security infrastructure is absent.

---

## 6. Gap Analysis Summary

Reconciling the 36 original requirements against actual implementation yields the following exact disposition pipeline:

```
ORIGINAL REQUIREMENT
        ↓
ACTUAL IMPLEMENTATION
        ↓
CURRENT STATUS
        ↓
DEPENDENCY
        ↓
NEXT APPROPRIATE GATE
```

### Table 6.1: Comprehensive Gap Analysis Disposition

| Original Requirement | Actual Implementation | Current Status | Dependency | Next Appropriate Gate |
| :--- | :--- | :--- | :--- | :--- |
| **1–7. HS256 JWT Verification** | `backend/interfaces/http/v2/security/jwt.py` | **IMPLEMENTED** | Python stdlib (`hmac`, `hashlib`) | **Gate 06** (Preserved) |
| **8–13. WhatsApp Signature Verification** | `backend/interfaces/http/v2/webhooks/whatsapp/signature.py` | **IMPLEMENTED** | Python stdlib (`hmac`, `hashlib`) | **Gate 06** (Preserved) |
| **14–16. WhatsApp Handshake** | `backend/interfaces/http/v2/webhooks/whatsapp/verify_token.py` | **IMPLEMENTED** | Python stdlib (`secrets`) | **Gate 06** (Preserved) |
| **17. Inbound Envelope Normalization** | `backend/interfaces/http/v2/webhooks/whatsapp/envelope.py` | **IMPLEMENTED** | Pure Python dataclass | **Gate 06** (Preserved) |
| **18. OpenAPI / Request Schema Boundary** | None | **NOT YET IMPLEMENTED** | Pydantic v2 DTOs, HTTP Router | **Gate 07** |
| **19. Security Error Boundary** | Verifier exceptions typed; no HTTP handlers | **PARTIAL** | FastAPI Exception Handlers | **Gate 07** |
| **20. RBAC Authorization Policy** | Role token mapping only (`roles.py`) | **BLOCKED BY MISSING CONTRACT** | `AuthenticatedContext`, `AuthorizationPolicy` | **Gate 07** (Coarse RBAC) |
| **21. Caregiver Relationship Authz** | None (Domain entity exists only) | **BLOCKED BY MISSING CONTRACT** | `CaregiverRelationshipRepository` + Schema + RLS | **Gate 08** |
| **22. Tenant Isolation at HTTP Boundary** | Gate 05 RLS exists; HTTP binding absent | **PARTIAL** | `AuthenticatedContext` $\rightarrow$ `UnitOfWork` | **Gate 07** |
| **23. Patient Self-Access Identity Bridge** | None | **BLOCKED BY MISSING CONTRACT** | `IdentityPatientMappingPort` + Phone Claim | **Gate 08** |
| **24. Caregiver Unlinked Patient Deny** | None | **BLOCKED BY MISSING CONTRACT** | `CaregiverRelationshipRepository` port/model | **Gate 08** |
| **25. Clinician Cross-Facility Deny** | None | **BLOCKED BY MISSING CONTRACT** | Facility assignment policy in `AuthorizationPolicy` | **Gate 08** |
| **26. Authorized Relationship Allow** | None | **BLOCKED BY MISSING CONTRACT** | Relationship repository + policy | **Gate 08** |
| **27–28. Webhook Replay & Idempotency** | None (Delegated in docstring) | **BLOCKED BY MISSING CONTRACT** | `IdempotencyStore` port + Redis/SQL adapter | **Gate 09** |
| **29. Rate Limiting** | None | **BLOCKED BY MISSING CONTRACT** | `RateLimiter` port + Redis adapter | **Gate 09** |
| **30. Audit Event Boundary** | None | **BLOCKED BY MISSING CONTRACT** | `AuditStore` port + `AuditEvent` model | **Gate 09** |
| **31. PHI Redaction in Logging** | Gate 05 `InfrastructureLogger` implemented | **IMPLEMENTED** | Python `logging` filter | **Gate 05** (Preserved) |
| **32. Channel Envelope PHI Exclusion** | `WhatsAppInboundEnvelope` carries no PHI | **IMPLEMENTED** | Envelope dataclass design | **Gate 06** (Preserved) |
| **33. HTTP Transport & Routers** | None | **NOT YET IMPLEMENTED** | FastAPI, Uvicorn, ASGI | **Gate 07** |
| **34. OpenAPI Exposure Policy** | None | **NOT YET IMPLEMENTED** | FastAPI `openapi_url` configuration | **Gate 07** |
| **35. HTTP Dependency Injection** | None | **NOT YET IMPLEMENTED** | FastAPI `Depends()`, Container wiring | **Gate 07** |
| **36. 500 Stack Trace Suppression** | None | **NOT YET IMPLEMENTED** | Starlette Middleware, CORS, Headers | **Gate 07** |

---

## 7. Dependency Graph

The execution of API requests involves three distinct dependency graphs: Identity/Authorization, Webhook Processing, and HTTP Transport.

### 7.1 Primary Identity & Authorization Dependency Graph

```
                            JWT / OIDC Token
                                   │
                                   ▼
                       [Authentication Extraction]
                    (Gate 06 verify_hs256 / Gate 05 Keycloak)
                                   │
                                   ▼
                         AuthenticatedContext  ◄── [MISSING CONTRACT]
                         (actor_id, tenant_id, roles)
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
               [tenant_id]                   [Role Tokens]
                    │                             │
                    ▼                             ▼
            SqlAlchemyUnitOfWork             Coarse RBAC Policy  ◄── [MISSING CONTRACT]
           (Gate 05, implemented)                 │
                    │                             ▼
                    ▼                 Relationship Authorization ◄── [BLOCKED BY MISSING
          transaction-local RLS       (CaregiverRelationshipRepo)     CONTRACTS IN GATE 04/05]
        set_config('app.current_tenant_id')       │
                    │                             ▼
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                        Application Use Case
                      (Gate 04, 12 handlers)
                                   │
                                   ▼
                              Domain Model
                        (Gate 03, pure entities)
```

### 7.2 WhatsApp Channel Dependency Graph

```
WhatsApp Inbound Webhook
   │
   ├── [Raw-Body HMAC-SHA256]         ──► [EXISTS: Gate 06 signature.py]
   │
   ├── [Handshake Challenge]          ──► [EXISTS: Gate 06 verify_token.py]
   │
   ├── [PHI-Minimal Envelope]         ──► [EXISTS: Gate 06 envelope.py]
   │
   ├── [Replay Protection / Dedup]    ──► [DOES NOT EXIST: Missing IdempotencyStore port]
   │
   ├── [HTTP Webhook Router]          ──► [DOES NOT EXIST: No route mounted]
   │
   └── [Application Invocation]       ──► [DOES NOT EXIST: No worker/service wired]
```

### 7.3 HTTP Transport Boundary Graph

```
FastAPI HTTP Request
   │
   ├── [Request DTO Validation]       ──► [DOES NOT EXIST: No Pydantic v2 schemas]
   │
   ├── [Authentication Dependency]    ──► [PARTIAL: Crypto exists; HTTP Depends absent]
   │
   ├── [Coarse Authorization]         ──► [DOES NOT EXIST: No AuthorizationPolicy]
   │
   ├── [Rate Limiting]                ──► [DOES NOT EXIST: No RateLimiter port]
   │
   ├── [Idempotency Key]              ──► [DOES NOT EXIST: No IdempotencyStore port]
   │
   ├── [Correlation ID Middleware]    ──► [DOES NOT EXIST: No middleware implemented]
   │
   ├── [Audit Event Store]            ──► [DOES NOT EXIST: No AuditStore port]
   │
   └── [Error Boundary / Safe 500]    ──► [DOES NOT EXIST: No exception handlers]
```

---

## 8. Contract Dependency Analysis

Section 6 of the reconciliation prompt requires evaluating seven specific contracts to determine their exact architectural dependency relative to the HTTP security boundary.

### Table 8.1: Critical Contract Prerequisite Analysis

| # | Contract / Capability | Dependency Category | Justification from Existing Contracts |
| :---: | :--- | :--- | :--- |
| **1** | `AuthenticatedContext` | **CAN BE INTRODUCED WITH HTTP** | Defined in application ports as a value object (`actor_id`, `tenant_id`, `roles`, `facility_id`). The HTTP authentication dependency instantiates this context immediately after JWT cryptographic verification and passes it inward. |
| **2** | `AuthorizationPolicy` | **CAN BE INTRODUCED WITH HTTP** | Coarse role-based authorization (`can_create_medication_plan`, `can_review_ai_artifact`) maps directly to Gate 03 entity capabilities on `CareTeamMember`. The policy port/engine can be introduced at the HTTP boundary to guard endpoints. |
| **3** | `IdentityPatientMappingPort` | **REQUIRED BEFORE PATIENT SELF-ACCESS** | Neither Gate 03, 04, nor 05 provides any mechanism to link an authenticated Keycloak user identity (`sub`) or verified phone claim to a domain `PatientProfile`. Patient self-access endpoints MUST NOT be exposed until this contract exists. |
| **4** | `CaregiverRelationshipRepository` | **REQUIRED BEFORE CAREGIVER ACCESS** | Gate 03 defined `CaregiverRelationship` as a pure entity, but Gate 04 omitted a repository port, and Gate 05 omitted the table model, migration, and RLS policy. Exposing caregiver access to patient data without this repository would force universal access. |
| **5** | `IdempotencyStore` | **CAN SAFELY FOLLOW HTTP** | Basic HTTP transport and read operations do not require an idempotency store. State-changing write endpoints can enforce validation and RLS; replay protection can be added as a decorator/dependency before production cutover. |
| **6** | `RateLimiter` | **CAN SAFELY FOLLOW HTTP** | Rate limiting is an operational resilience control, not an architectural integrity prerequisite. It can be introduced as middleware once the HTTP transport exists. |
| **7** | `AuditStore` | **CAN SAFELY FOLLOW HTTP** | Gate 05 already provides privacy-preserving structured logging (`InfrastructureLogger`). The formal append-only `AuditStore` port for compliance event persistence can follow the core HTTP boundary. |

---

## 9. Candidate Gate Structures

Four structural options for structuring the next phase of work were evaluated.

### 9.1 Candidate A: Gate 07 = Complete Monolithic API & Security Boundary
- **Description**: Implement all 18 missing requirements in a single massive Gate 07 (FastAPI, DI, DTOs, JWT $\rightarrow$ RLS binding, RBAC, caregiver repository, patient identity mapping, idempotency store, rate limiter, audit store, webhook endpoint).
- **Advantages**: Restores the original Gate 02A / Gate 06 vision in a single step.
- **Disadvantages**: Enormous scope; mixes transport, database schema migrations (for caregiver relationships), application ports, and operational stores; extreme review complexity; high failure risk.
- **Dependency Correctness**: **POOR**. Forces schema and port extraction to happen inside an "interface" gate.
- **Security Correctness**: **DANGEROUS**. High likelihood of faking missing contracts to get the API working.

### 9.2 Candidate B: Gate 07 = HTTP Transport Only (Split Security Completely)
- **Description**: Gate 07 builds unauthenticated FastAPI routes, then Gate 08 adds security.
- **Advantages**: Fast, simple implementation.
- **Disadvantages**: Commits an unauthenticated, insecure HTTP attack surface to the repository.
- **Dependency Correctness**: **POOR**. Violates the clean architecture principle that security is part of the transport boundary.
- **Security Correctness**: **UNACCEPTABLE**. Merging unauthenticated routes into `develop` violates clinical safety rules.

### 9.3 Candidate C: Gate 07 = Contracts First, Gate 08 = HTTP Implementation
- **Description**: Gate 07 defines `AuthenticatedContext`, `CaregiverRelationshipRepository`, `IdentityPatientMappingPort`, `IdempotencyStore`, and `AuditStore`. Gate 08 implements HTTP.
- **Advantages**: Clean contract definition.
- **Disadvantages**: Leaves the HTTP layer unbuilt for another gate cycle; creates ports without active consumers in the same gate.
- **Dependency Correctness**: Moderate.

### 9.4 Candidate D: Disciplined Dependency-Ordered Decoupling (RECOMMENDED)
- **Description**: Structure the progression into three focused, dependency-correct gates:
  1. **Gate 07: HTTP Transport, Dependency Injection & Security Boundary**: Builds the FastAPI app factory, HTTP DI, `AuthenticatedContext`, JWT $\rightarrow$ RLS binding, coarse RBAC, safe error handling, security headers, health checks, and the WhatsApp webhook endpoint. Caregiver and patient self-access remain strictly **deny-by-default**.
  2. **Gate 08: Relational Identity & Clinical Authorization**: Establishes `CaregiverRelationshipRepository` (port, SQLAlchemy model, Alembic migration, RLS policy), `IdentityPatientMappingPort`, and fine-grained relationship authorization handlers.
  3. **Gate 09: Operational Resiliency, Idempotency & Channel Orchestration**: Establishes `IdempotencyStore`, `RateLimiter`, `AuditStore`, and webhook async command processing.
- **Advantages**: 
  - Resolves the critical security chain (JWT $\rightarrow$ `AuthenticatedContext` $\rightarrow$ UoW $\rightarrow$ RLS) immediately.
  - Exposes an authenticated, hardened HTTP surface with zero unauthenticated endpoints.
  - Eliminates shortcuts: caregiver and patient self-access remain fail-closed until Gate 08 establishes their database contracts.
  - Clean separation of concerns; each gate has a well-defined test matrix.
- **Dependency Correctness**: **EXCELLENT**. Follows natural architectural dependencies.
- **Security Correctness**: **MAXIMAL**. Strict deny-by-default; no universal role access; RLS verified end-to-end.

---

## 10. Security Boundary Analysis

### 10.1 Caregiver and Patient Identity (Section 7 Reconciliation)
A role alone must **never** grant access to patient clinical records:
- `role: DOCTOR` $\ne$ access to all patients. Access must be scoped to the assigned facility or care team.
- `role: CAREGIVER` $\ne$ access to all patients. Access is valid **only** if an active, non-revoked `CaregiverRelationship` record explicitly binds the caregiver's `user_id` to the target `patient_id`.
- `role: PATIENT` $\ne$ arbitrary access via `GET /patients/{id}`. Access is valid **only** if the caller's verified identity matches the patient persona.

Because `CaregiverRelationship` has no repository port, database model, or RLS policy today, and because `IdentityPatientMappingPort` does not exist:
> [!CRITICAL]
> In Gate 07, any request by a caregiver to access patient data, or any request by a user claiming patient self-access, **MUST return HTTP 403 Forbidden (deny-by-default)**. These capabilities will be unlocked exclusively in Gate 08 after their persistence and identity contracts are fully implemented and verified.

### 10.2 Tenant Security & The Authoritative RLS Chain (Section 8 Reconciliation)
Gate 05 established the database mechanism for tenant isolation:
```sql
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON patients
  USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
```
Gate 05 also verified that `SqlAlchemyUnitOfWork._apply_tenant_context()` calls `set_config('app.current_tenant_id', :tid, true)` inside the transaction.

However, **this chain is currently broken at the HTTP transport boundary**:
```
Verified JWT Token
       ↓ (Claims contain tenant_id)
FastAPI HTTP Request (NO ADAPTER)
       ↓ (tenant_id is NEVER passed)
SqlAlchemyUnitOfWork(tenant_id=None)
       ↓
set_config('app.current_tenant_id', '')
       ↓
PostgreSQL RLS fails closed (0 rows returned) or cross-tenant query succeeds if RLS bypassed
```
**Gate 07 is the mandatory architectural gate to close this chain**:
1. FastAPI dependency extracts `tenant_id` from the verified JWT.
2. The dependency instantiates `AuthenticatedContext(tenant_id=...)`.
3. The dependency injects `tenant_id` directly into `SqlAlchemyUnitOfWork(session_factory, tenant_id=context.tenant_id)`.
4. The UoW executes `set_config('app.current_tenant_id', :tid, true)`.
5. Integration security tests verify that cross-tenant access returns HTTP 403 or 404.

### 10.3 WhatsApp Webhook Security (Section 9 Reconciliation)
The WhatsApp channel boundary is partitioned across gates:
1. **Cryptographic Verification**: **IMPLEMENTED (Gate 06)** via `verify_x_hub_signature_256` and `challenge_response`.
2. **HTTP Webhook Endpoint**: **GATE 07** introduces `POST /api/v2/webhooks/whatsapp` and `GET /api/v2/webhooks/whatsapp`. It verifies signatures over the raw request body bytes and normalizes payloads into `WhatsAppInboundEnvelope`.
3. **Replay Protection & Deduplication**: **GATE 09** introduces `IdempotencyStore` to record seen `message_id`s before processing.
4. **Application Invocation & Asynchronous Processing**: **GATE 09** connects verified envelopes to application command handlers (`IngestGlucoseReading`, `LogMealDraft`) via background worker queues.

---

## 11. Git & Checkpoint Preservation

Section 10 of the reconciliation prompt requires evaluating three formal options regarding the status of Gate 06.

### Table 11.1: Evaluation of Gate 06 Status Options

| Criteria | Option 1: Keep Gate 06 Open | Option 2: Create Gate 06 Completion Gate | Option 3: Redefine Gate 06 as Primitive Milestone (RECOMMENDED) |
| :--- | :--- | :--- | :--- |
| **Git Integrity** | **POOR**. Requires amending or adding commits to `feature/gate-06-api-security`, risking tag detachment. | **MODERATE**. Creates messy "Gate 06B" branch and tag proliferation. | **EXCELLENT**. Preserves commit `c6c7614` and tag `gate-06-api-security-complete` exactly as they exist. |
| **Auditability** | **POOR**. Obscures what was built when. | **MODERATE**. Confusing split lineage. | **EXCELLENT**. Clear documentation of cryptographic primitives at `c6c7614`. |
| **Frozen Architecture** | **VIOLATED**. Gate 06 becomes an unbounded container. | **MODERATE**. Ad-hoc fraction gates weaken structure. | **PRESERVED**. Gate 06 is frozen; Gate 07 starts with clean scope. |
| **Security Correctness** | **DANGEROUS**. Tempts developer to rush HTTP and authz in one commit. | **ACCEPTABLE**. | **MAXIMAL**. Enforces clean dependency ordering across Gates 07, 08, and 09. |
| **Migration Sequencing** | Confusing. | Disruptive to Gate 02A alignment. | **ALIGNED**. Re-anchors roadmap to clean architectural boundaries. |

### 11.1 Immutable Governance Rules
In accordance with Option 3:
- **DO NOT** amend `c6c7614`.
- **DO NOT** move or delete tag `gate-06-api-security-complete`.
- **DO NOT** rewrite Gate 03, Gate 04, or Gate 05 documentation or code.
- **DO NOT** create implementation commits or new Git tags during this reconciliation.
- **DO NOT** modify source code or tests.

---

## 12. Recommended Gate Sequence

The authoritative sequence for the THALI × P.L.A.T.E. Production Program is established as follows:

```
================================================================================
CURRENT STATE:
Gate 05 = APPROVED (Commit: 5503ad0d4f986fea5ebd88b3db988b0c8b4b4cde)
Gate 06 = PARTIALLY COMPLETE (Cryptographic Primitives Frozen at c6c7614)
Gate 07 = LOCKED (Pending Reconciliation Approval)
================================================================================
RECOMMENDED GOVERNANCE SEQUENCE:
Gate 06 = CLOSED AS CRYPTOGRAPHIC PRIMITIVES MILESTONE (c6c7614)
Gate 07 = HTTP TRANSPORT, DEPENDENCY INJECTION & SECURITY BOUNDARY
Gate 08 = RELATIONAL IDENTITY & CLINICAL AUTHORIZATION
Gate 09 = OPERATIONAL RESILIENCY, IDEMPOTENCY & CHANNEL ORCHESTRATION
Gate 10 = CLIENT MONOREPO SCAFFOLDING & ENTERPRISE CUTOVER
================================================================================
```

---

## 13. Recommended Gate 07 Scope: HTTP Transport, Dependency Injection & Security Boundary

### Purpose
Establish the physical HTTP transport boundary, FastAPI application factory, dependency injection architecture, and authoritative multi-tenant security binding (JWT $\rightarrow$ `AuthenticatedContext` $\rightarrow$ `UnitOfWork` $\rightarrow$ PostgreSQL RLS), enabling secure execution of clinical use cases.

### Scope
1. **FastAPI Application Factory** (`backend/interfaces/http/app.py`):
   - `create_app()` factory function.
   - Global exception handlers mapping domain exceptions to safe, standardized HTTP JSON responses.
   - Suppression of 500 internal server error stack traces.
   - Security middleware: CORS configuration, Security Headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options).
   - Health and readiness endpoints (`/health/live`, `/health/ready`).
2. **HTTP Dependency Injection Container** (`backend/interfaces/http/dependencies.py`):
   - `get_jwt_verifier()`: Consumes Gate 06 `verify_hs256`.
   - `get_authenticated_context()`: Decodes Bearer token, extracts `actor_id`, `tenant_id`, and roles, returns `AuthenticatedContext`.
   - `get_unit_of_work()`: Instantiates `SqlAlchemyUnitOfWork` pre-bound to `AuthenticatedContext.tenant_id`.
   - `get_current_user()` and `require_role(roles)` dependencies.
3. **Enterprise Route Registration** (`backend/interfaces/http/v2/`):
   - `/api/v2/auth/verify`: Token validation and claims introspection endpoint.
   - `/api/v2/webhooks/whatsapp`: GET (challenge handshake) and POST (raw-body verified inbound receiver).
   - `/api/v2/clinical/observations`: Clinician observation feed endpoint (guarded by `CareTeamRole`).
   - `/api/v2/clinical/medication-plans`: Medication plan authoring (strictly clinician-only).
   - `/api/v2/clinical/ai-artifacts`: AI review artifact list and review approval (licensed clinician only).
4. **Coarse RBAC Authorization Engine**:
   - `AuthorizationPolicy` evaluating role capabilities against Gate 03 `CareTeamRole` definitions.
   - Deny-by-default for missing permissions.
5. **Enforced Relationship Deny-by-Default**:
   - Any access to patient-specific endpoints by caregivers or self-accessing patients returns **HTTP 403 Forbidden** with an explicit error code indicating that relationship authorization contracts are pending Gate 08.

### Inputs
- Gate 03 Domain Entities & Invariants.
- Gate 04 Application Use Cases & Outbound Ports.
- Gate 05 `SqlAlchemyUnitOfWork`, PostgreSQL RLS, and `KeycloakTokenValidator`.
- Gate 06 `verify_hs256`, `verify_x_hub_signature_256`, `challenge_response`, and `WhatsAppInboundEnvelope`.

### Outputs
- Operational FastAPI application mounting `/api/v2` and `/health`.
- HTTP dependency injection graph binding JWT to transaction-local RLS.
- OpenAPI specification with environment-gated visibility.
- Integration test suite validating HTTP security, RBAC enforcement, and tenant RLS boundary.

### Security Boundary
- All endpoints except `/health` and `/api/v2/webhooks/whatsapp` require valid Bearer JWT.
- WhatsApp webhook requires byte-exact HMAC-SHA256 signature verification over raw body bytes.
- Tenant context is strictly bound from verified JWT claims to PostgreSQL RLS via UoW.
- No stack traces leaked in HTTP responses.
- Caregiver and patient self-access remain strictly blocked (deny-by-default).

### Required Contracts
- `AuthenticatedContext` (Value Object in application ports or interfaces).
- `AuthorizationPolicy` (Coarse RBAC evaluation interface).
- Request/Response Pydantic v2 DTOs for observation feeds, medication plans, and AI artifacts.

### Required Tests
- HTTP authentication: Missing token $\rightarrow$ 401; invalid signature $\rightarrow$ 401; expired token $\rightarrow$ 401.
- Tenant isolation at HTTP boundary: User from Tenant A cannot access Tenant B resources (returns 403/404); live PostgreSQL RLS verification.
- Coarse RBAC: Non-clinician creating medication plan $\rightarrow$ 403 Forbidden; Dietitian reviewing medical AI artifact $\rightarrow$ 403 Forbidden.
- Error boundary: Domain exceptions map to clean JSON; uncaught errors return generic 500 without stack trace.
- Webhook endpoint: Valid signature accepted $\rightarrow$ 200; tampered body rejected $\rightarrow$ 401/403.
- Handshake endpoint: Valid verify token echoes challenge; invalid token rejected.
- Caregiver/Patient deny-by-default: Explicit tests verifying that caregiver patient queries return 403 Forbidden.

### Exit Criteria
- [ ] FastAPI app factory (`create_app`) operational and tested.
- [ ] End-to-end JWT $\rightarrow$ `AuthenticatedContext` $\rightarrow$ `UnitOfWork` $\rightarrow$ PostgreSQL RLS chain verified green.
- [ ] Coarse RBAC enforced on all clinical routes.
- [ ] WhatsApp webhook HTTP endpoints mounted and passing signature verification tests.
- [ ] Security headers and safe error handlers active.
- [ ] Caregiver and patient self-access strictly fail-closed (403 Forbidden).
- [ ] Full test suite passing (226 existing + new Gate 07 HTTP tests).

### What Gate 07 Explicitly MUST NOT Contain
- ❌ **NO per-patient caregiver relationship authorization** (Deferred to Gate 08).
- ❌ **NO patient self-access endpoints** (Deferred to Gate 08).
- ❌ **NO arbitrary patient access for doctors** (No role-based universal access).
- ❌ **NO database migrations or new tables** (Persistence schema frozen at Gate 05).
- ❌ **NO webhook replay protection or dedup store** (Deferred to Gate 09).
- ❌ **NO rate limiting store** (Deferred to Gate 09).
- ❌ **NO compliance audit store** (Deferred to Gate 09).

---

## 14. Future Gate Scope

### 14.1 Gate 08: Relational Identity & Clinical Authorization
- **Purpose**: Implement the missing domain repository ports, database models, migrations, and authorization services required to securely verify caregiver-to-patient relationships and patient self-access identity mapping.
- **Scope**:
  1. `CaregiverRelationshipRepository` port in `backend/application/ports/repositories.py`.
  2. `CaregiverRelationshipModel` in `backend/infrastructure/persistence/models/`.
  3. Alembic migration creating `caregiver_relationships` table with foreign keys and PostgreSQL RLS policies.
  4. `SqlAlchemyCaregiverRelationshipRepository` implementing tenant-scoped relationship queries.
  5. `IdentityPatientMappingPort` resolving authenticated Keycloak identity (`sub`) and phone claims to domain `PatientProfile`.
  6. Fine-grained relationship authorization service: verifying clinician facility assignment, active caregiver proxy authorization, and patient own-record verification.
  7. Exposing `/api/v2/patients/{id}/` endpoints to authorized caregivers and self-accessing patients.
- **Exit Criteria**:
  - Live PostgreSQL RLS tests proving a caregiver cannot access an unlinked patient.
  - Integration tests proving a patient cannot access another patient's IDOR route.
  - Zero role-based universal access shortcuts.

### 14.2 Gate 09: Operational Resiliency, Idempotency & Channel Orchestration
- **Purpose**: Deploy production operational security controls, replay protection, rate limiting, audit event trails, and decoupled intake channel processing.
- **Scope**:
  1. `IdempotencyStore` port + Redis/PostgreSQL adapter.
  2. Webhook replay protection: Deduplication by `message_id` before processing.
  3. `RateLimiter` port + Redis token bucket middleware (per tenant, user, and IP).
  4. `AuditStore` port + `AuditEvent` persistence for clinical data access and security events.
  5. Asynchronous webhook processing: Connecting verified `WhatsAppInboundEnvelope`s to application command handlers (`IngestGlucoseReading`, `LogMealDraft`) via background intake worker.

### 14.3 Gate 10: Client Monorepo Scaffolding & Enterprise Cutover
- **Purpose**: Initialize frontend client applications, execute dual-run data migration from legacy SQLite, and decommission legacy prototypes.
- **Scope**:
  1. React Native + Expo Universal Mobile App (`apps/mobile/`).
  2. React Admin Web Console (`apps/admin-web/`).
  3. One-way migration runner (`migrate_sqlite_to_postgres.py`) with parity validation.
  4. Decommissioning of legacy `app/static/` and monolithic SQLite `Store`.

---

## 15. Explicit Non-Goals

During the upcoming gates, the following anti-patterns and shortcuts are explicitly prohibited:
1. **NO Universal Access Bypasses**: Never allow `role == "doctor"` or `role == "admin"` to bypass tenant boundaries or access patients without facility/care-team association.
2. **NO Unlinked Caregiver Access**: Never allow a user with `role: CAREGIVER` to view or log data for a patient without an active, verified `CaregiverRelationship` record.
3. **NO Unverified Patient Self-Access**: Never trust an unverified `patient_id` claim in a JWT or route parameter without resolving it through `IdentityPatientMappingPort`.
4. **NO Pre-Verification Payload Parsing**: Never parse, inspect, or deserialize JSON request bodies before cryptographic signature verification succeeds.
5. **NO Information Asymmetry Leaks**: Never include carbohydrate gram estimates, glycemic index values, or clinical diagnosis text in patient-facing DTOs or WhatsApp responses.
6. **NO AI Autonomous Clinical Actions**: Never allow AI models to approve meal drafts, alter medication plans, or execute diagnostic commands without licensed clinician review.
7. **NO Gate Amending**: Never rewrite git history, amend approved gate tags, or alter frozen test baselines.

---

## 16. Exit Criteria

### Table 16.1: Gate Sequence Reconciliation Exit Checklist

- [x] Full Git history and tag lineage verified (`baseline-gate-00` $\rightarrow$ `gate-06-api-security-complete`).
- [x] All 226 tests passing green across baseline, domain, application, infrastructure, and security suites.
- [x] Original Gate 02A ten-phase migration sequence reconciled against physical repository tree.
- [x] All 36 original Gate 06 requirements classified into PRIMITIVE, BOUNDARY, INTEGRATION, CONTRACT, and INFRASTRUCTURE.
- [x] Root causes of Gate 06 incomplete status identified (missing HTTP transport + blocked identity contracts).
- [x] Dependency graphs for Identity, WhatsApp, and HTTP transport constructed.
- [x] Critical contract prerequisites analyzed for all 7 key architectural components.
- [x] Candidate gate structures evaluated across security, dependency, and migration risks.
- [x] Authoritative sequence recommended: Gate 06 (Primitives) $\rightarrow$ Gate 07 (HTTP/DI/Security) $\rightarrow$ Gate 08 (Relational Identity) $\rightarrow$ Gate 09 (Resiliency/Orchestration).
- [x] Gate 07 scope, security boundary, required tests, and explicit non-goals comprehensively specified.
- [x] Future scopes for Gates 08, 09, and 10 established.
- [x] Working tree clean; zero source code changes, zero test changes, zero Git modifications executed.

---

## 17. Final Architectural Decision

1. **Gate 06 Checkpoint Accepted as Cryptographic Primitive Milestone**:  
   Commit `c6c7614` and tag `gate-06-api-security-complete` are frozen as the verified implementation of pure stdlib cryptographic primitives (JWT HS256, WhatsApp HMAC-SHA256, verify-token challenge handshake, PHI-minimal envelope).
2. **Gate 07 Defined as HTTP Transport, Dependency Injection & Security Boundary**:  
   Gate 07 is authorized to proceed upon stakeholder approval, strictly scoped to the FastAPI application, HTTP DI, `AuthenticatedContext`, JWT $\rightarrow$ RLS binding, coarse RBAC, safe error handling, security headers, health checks, and the WhatsApp webhook endpoint. Caregiver and patient self-access remain strictly deny-by-default.
3. **Relational Identity Contracts Delegated to Gate 08**:  
   `CaregiverRelationshipRepository` and `IdentityPatientMappingPort` are scheduled for dedicated contract and persistence implementation in Gate 08.
4. **Resiliency and Operational Infrastructure Delegated to Gate 09**:  
   Idempotency, rate limiting, compliance audit event logging, and asynchronous webhook ingestion are scheduled for Gate 09.
5. **Gate 07 Implementation Remains LOCKED**:  
   No code on Gate 07 will be authored until this reconciliation document is formally reviewed and approved.

---
*Document sealed on 2026-09-15. Working tree clean. Zero source code changes.*
