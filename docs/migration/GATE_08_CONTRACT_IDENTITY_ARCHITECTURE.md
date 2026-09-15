# GATE 08 — Contract & Identity Architecture Analysis
## THALI × P.L.A.T.E. Production Program

**Document ID**: `GATE-08-CONTRACT-IDENTITY-ARCHITECTURE`  
**Classification**: Architectural Analysis & Formal Contract Freeze (Read-Only Blueprint)  
**Execution Date**: 2026-09-15  
**Current Working Branch**: `feature/gate-07-http-security`  
**Canonical Predecessor (Gate 07)**: `fc3e594` (`gate-07-http-security-complete`)  
**Status**: ARCHITECTURAL CORRECTIONS FROZEN (Gate 08A)  
**Implementation**: NOT STARTED (Gate 08 Locked)  
**Future Gate 09**: LOCKED  

---

## 1. Executive Summary

Gate 07 established a hardened HTTP transport boundary with deny-by-default coarse RBAC. In Gate 07, two role families remain intentionally and permanently denied:

- **patient** — empty permission set (no self-access)
- **caregiver** — empty permission set (no proxy access)

This fail-closed posture is architecturally correct: without a verified identity-to-patient bridge and without a persisted, queryable caregiver relationship, any access grant would constitute a critical security breach (IDOR or unauthorized clinical exposure). Gate 08 defines the **exact contracts, persistence models, and authorization design** required to safely unlock patient self-access and caregiver proxy monitoring.

During final architectural review, four critical issues were identified and are formally corrected and frozen in this document (Gate 08A):

1. **Caregiver Relationship Lifecycle Authority**: Eliminate dual lifecycle authorities (`active` boolean vs `status` enum). The lifecycle is governed exclusively by a canonical `status` enum (`PENDING`, `VERIFIED`, `REVOKED`, `EXPIRED`). There is **no persistent `active` column**. Time-bounded validity (`expires_at`) is evaluated at request time by application authorization, failing closed without reliance on an asynchronous scheduler.
2. **Identity Mapping Authority & Administrative Isolation**: Identity-to-patient mappings (`IdentityPatientMapping`) are strictly administrative workflows. There is **no self-service mapping endpoint**, no SMS/phone binding, and no trust in unverified JWT claims. Administrative mapping authority is governed by an explicit capability (`MANAGE_IDENTITY_PATIENT_MAPPINGS`), strictly decoupled from clinical data access (`admin` cannot view patient clinical charts).
3. **Caregiver Operation-Level Authorization**: A verified caregiver relationship does **not** grant blanket access to patient records. Authorization enforces a strict two-tier check: relationship verification followed by an operation-level capability check. An explicit Phase-1 caregiver capability matrix allows observational logging and task management while strictly denying clinical modifications (medication plans, AI review, diagnosis).
4. **Clinician Facility Authorization & Stale JWT Mitigation**: JWT claims (`facility_id`) cannot serve as the authoritative clinical access source due to token refresh lag. Clinical facility authorization is anchored in current, server-side `CareTeamMember` records looked up via `sub`. If a JWT `facility_id` claim conflicts with the database `CareTeamMember.facility_id`, the system **fails closed (DENY)**.

Gate 08 solves these challenges while strictly preserving all existing Gate 03–07 invariants.

---

## 2. Current Gate Checkpoints

| Gate | Commit SHA | Annotated Git Tag | Test Suite Count | Status | Notes |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **Gate 05** | `5503ad0` | `gate-05-infrastructure-adapters-complete` | 209 | **SEALED** | PostgreSQL persistence, RLS engine, Alembic |
| **Gate 06** | `c6c7614` | `gate-06-api-security-complete` | 226 | **SEALED** | Cryptographic primitives (HS256, HMAC, envelope) |
| **Gate 07** | `fc3e594` | `gate-07-http-security-complete` | 321 | **SEALED** | FastAPI app, JWT $\rightarrow$ RLS binding, coarse RBAC |
| **Gate 08** | *None* | *None* | — | **LOCKED** | Contract & Architecture Freeze (Gate 08A) |
| **Gate 09** | *None* | *None* | — | **LOCKED** | Resiliency, Idempotency & Channel Orchestration |

Full test suite at Gate 07 close: **321 passed, 0 failed** (57 baseline + 48 Gate 03 + 49 Gate 04 + 55 Gate 05 + 17 Gate 06 + 95 Gate 07).

---

## 3. Existing Domain Identity Model

### 3.1 Patient (`backend/domain/entities/patient.py`)

| Field | Type | Notes |
| :--- | :--- | :--- |
| `id` | `UUID` | Aggregate root primary key |
| `uh_id` | `UHID` (value object) | Unique Hospital ID string, 3–32 characters |
| `name` | `str` | Patient legal name |
| `phone` | `PhoneNumber \| None` | E.164-normalized, log-masked contact number |
| `facility_id` | `UUID \| None` | Foreign key to `facilities` at ORM level; nullable |
| `active` | `bool` | `deactivate()` / `reactivate()` lifecycle |
| `created_at` | `datetime` | Creation timestamp |

**Invariants**:
- Tenant ownership is an infrastructure property enforced by `SqlAlchemyPatientRepository` and PostgreSQL RLS.
- Domain methods: `link_phone()`, `unlink_phone()`, `deactivate()`, `reactivate()`.
- Contact phone is **not** an authentication credential or identity bridge.

### 3.2 CaregiverRelationship (`backend/domain/entities/caregiver_relationship.py`) — As Defined in Gate 03

| Field | Type | Notes |
| :--- | :--- | :--- |
| `id` | `UUID` | Primary key |
| `patient_id` | `UUID` | Target patient identifier |
| `caregiver_user_id` | `UUID` | Keycloak subject (`sub`) of the caregiver |
| `relationship` | `str` | Label (e.g., "spouse", "parent") — non-empty string |
| `active` | `bool` | Gate 03 legacy boolean flag (revoke-only) |
| `created_at` | `datetime` | Creation timestamp |

**Existing Gate 03 Contract & Invariant**:
- Revoke-only lifecycle: `revoke()` transitions the relationship to inactive.
- If already inactive, `revoke()` raises `InvalidRelationship("caregiver relationship is already revoked")`.
- Re-revocation is strictly forbidden.

**Identified Gaps to Close in Gate 08**:
- No `tenant_id` at domain entity level.
- Missing explicit lifecycle enum (`PENDING`, `VERIFIED`, `REVOKED`, `EXPIRED`).
- No `expires_at` validity boundary.
- No repository port or persistence implementation.

### 3.3 CareTeamMember (`backend/domain/entities/care_team_member.py`)

| Field | Type | Notes |
| :--- | :--- | :--- |
| `id` | `UUID` | Aggregate identity |
| `user_id` | `UUID` | **Keycloak subject (`sub`)** — identity $\rightarrow$ clinician bridge |
| `role` | `CareTeamRole` | Enum: `DOCTOR`, `NURSE`, `CARE_COORDINATOR`, `DIETITIAN`, `FIELD_HEALTH_WORKER` |
| `display_name` | `str` | Clinician display name |
| `facility_id` | `UUID \| None` | Clinician's authorized facility |
| `active` | `bool` | Active membership flag |

**Authority Invariants**:
- `CareTeamRole.can_author_medication` $\rightarrow$ `{DOCTOR, NURSE, DIETITIAN}`.
- This entity is the authoritative server-side anchor for clinician facility assignment and clinical capability.

### 3.4 Facility & Organization Persistence Models

- `FacilityModel` (`facilities` table): `id`, `tenant_id`, `name`, `active`, `created_at`.
- `OrganizationModel` (`organizations` table): `id`, `name`, `slug`, `active`, `created_at`. Root tenant anchor.

---

## 4. Existing Application Contracts

### 4.1 UnitOfWork Protocol (`backend/application/ports/unit_of_work.py`)

The Gate 04 `UnitOfWork` protocol manages transactional boundaries:
```python
class UnitOfWork(Protocol):
    patients: PatientRepository
    care_team_members: CareTeamMemberRepository
    glucose_observations: GlucoseObservationRepository
    meal_observations: MealObservationRepository
    medication_plans: MedicationPlanRepository
    care_tasks: CareTaskRepository
    ai_artifacts: AIReviewArtifactRepository
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```
*Current Gap*: Lacks `caregiver_relationships` and `identity_mappings` attributes.

### 4.2 Existing Repository Ports (`backend/application/ports/repositories.py`)

Gate 04 established 7 typed repository protocols:
- `PatientRepository`: `add`, `get(patient_id)`, `save`, `list`.
- `CareTeamMemberRepository`: `add`, `get(user_id)`, `list` (keyed by Keycloak `user_id`).
- `GlucoseObservationRepository`, `MealObservationRepository`, `MedicationPlanRepository`, `CareTaskRepository`, `AIReviewArtifactRepository`.

*Current Gap*: `CaregiverRelationshipRepository` and `IdentityPatientMappingRepository` were explicitly excluded in Gate 04 and must be defined in Gate 08.

---

## 5. Existing Infrastructure & Security Foundation (Gate 05–07)

### 5.1 AuthenticatedContext (`backend/interfaces/http/dependencies.py`)

Gate 07 established the immutable request context:
```python
@dataclass(frozen=True)
class AuthenticatedContext:
    actor_id: UUID          # Keycloak sub claim
    tenant_id: UUID         # Verified tenant_id claim
    roles: tuple[str, ...]  # Coarse realm roles
    facility_id: UUID | None = None  # Claimed facility hint
    username: str = ""
```

### 5.2 Tenant Isolation & PostgreSQL RLS Lifecycle

Every HTTP request traverses the authoritative chain established in Gate 07:
```
Verified JWT (HS256)
  ↓
AuthenticatedContext { actor_id, tenant_id, roles, facility_id }
  ↓
SqlAlchemyUnitOfWork(session_factory, tenant_id=ctx.tenant_id)
  ↓
set_config('app.current_tenant_id', :tid, true) [Transaction-Local SET LOCAL]
  ↓
PostgreSQL RLS Filters on All TENANT_TABLES
```

---

## 6. Architectural Corrections Frozen Under Gate 08A

---

### CORRECTION 1: Caregiver Relationship Lifecycle & Expiration

#### 1. Single Lifecycle Authority: The `status` Enum
To prevent state desynchronization and security ambiguity, **there shall not be two independent lifecycle authorities**. The persistent boolean column `active` is completely eliminated from the Gate 08 persistence model. The lifecycle is controlled exclusively by the `status` enum:

$$\text{CaregiverRelationshipStatus} \in \{\text{PENDING}, \text{VERIFIED}, \text{REVOKED}, \text{EXPIRED}\}$$

#### 2. Authoritative Authorization Condition
A caregiver relationship permits authorization if and only if:
```python
status == CaregiverRelationshipStatus.VERIFIED
and (expires_at is None or expires_at > current_time)
```

#### 3. Canonical Domain State Machine Transitions
All state transitions must be explicit. Any undefined transition must fail closed by raising `InvalidStateTransition` or `InvalidRelationship`:
- `PENDING → VERIFIED`: Clinician or administrative verification.
- `VERIFIED → REVOKED`: Explicit revocation by patient, caregiver, or clinician.
- `VERIFIED → EXPIRED`: Transitioned upon passing validity window.
- `PENDING → REVOKED`: Rejection/cancellation of an unverified relationship.

```
       ┌───────────┐
       │  PENDING  │
       └─────┬─────┘
             │
      verify │      \ revoke
             ▼       ▼
       ┌───────────┐   ┌───────────┐
       │ VERIFIED  ├──►│  REVOKED  │ (Terminal)
       └─────┬─────┘   └───────────┘
             │ expire        ▲
             ▼               │ revoke
       ┌───────────┐         │
       │  EXPIRED  ├─────────┘
       └───────────┘
```

#### 4. Revocation Invariants
In alignment with the Gate 03 contract, `revoke()` transitions the relationship to `REVOKED` and records `revoked_at`. If the relationship is already in `REVOKED` status, invoking `revoke()` raises `InvalidRelationship("caregiver relationship is already revoked")`. Revocation is irreversible.

#### 5. Request-Time Expiration Semantics (No Scheduler Dependency)
`expires_at` is an authoritative security boundary, not passive metadata. Application-level authorization checks evaluate expiration at request time against the system clock:
- If `expires_at <= current_time`, authorization **MUST DENY (HTTP 403)** immediately.
- Authorization correctness does **not** depend on a Gate 09 background worker or cron scheduler to physically update the database row to `EXPIRED`. An un-transitioned row whose timestamp has lapsed fails closed at runtime.

---

### CORRECTION 2: Identity Mapping Authority & Administrative Isolation

#### 1. Contract & Invariants
`IdentityPatientMapping` binds an authenticated Keycloak user identity (`sub`) to a domain `PatientProfile`:
- **Tenant-Scoped**: Stored with `tenant_id` and enforced by PostgreSQL RLS.
- **Keycloak Anchor**: `user_id` corresponds to the cryptographically verified JWT `sub`.
- **Domain Anchor**: `patient_id` corresponds to the canonical `Patient` aggregate root.
- **Strict 1:1 Cardinality**:
  - Exactly one active mapping per `user_id` per tenant.
  - Exactly one active mapping per `patient_id` per tenant.

#### 2. No Self-Service Mapping Endpoints
There is **NO self-service identity mapping endpoint** (`/api/v2/patients/self/link` or similar is strictly forbidden). Self-service binding introduces severe account-takeover risks.
- No client-supplied JWT `patient_id` claims are trusted.
- No unverified phone/SMS binding mechanisms are permitted in Phase 1.
- All mapping creations, mutations, and deactivations are **administrative workflows only**.

#### 3. Strict Separation of Administration and Clinical Data Access
To prevent the creation of a universal administrative backdoor:
- An administrative user possessing the authority to manage identity mappings does **NOT** receive healthcare or clinical data access.
- We define an explicit application capability:
  $$\text{Capability: } \text{MANAGE\_IDENTITY\_PATIENT\_MAPPINGS}$$
- Only an actor holding this specific capability in an active administrative role may create or deactivate mappings.
- The authorization policy forbids blanket administrative checks such as:
  ```python
  # STRICTLY FORBIDDEN ANTI-PATTERN:
  if "admin" in ctx.roles:
      allow_all()
  ```
- An administrator querying clinical routes (`/api/v2/clinical/observations`) will be denied (HTTP 403) unless they hold an active, clinical `CareTeamMember` role at the authorized facility.

---

### CORRECTION 3: Caregiver Operation-Level Authorization Matrix

#### 1. Two-Tier Authorization Model
A verified caregiver relationship confirms the *existence of a proxy link*, but does **not** grant unrestricted patient access. Authorization is evaluated in two distinct phases:
1. **Relationship Verification**: The caregiver possesses an unexpired, `VERIFIED` relationship for the target patient.
2. **Operation Capability**: The requested action is explicitly permitted in the Caregiver Capability Matrix.

#### 2. The 9-Step Caregiver Authorization Sequence
Every caregiver request targeting patient resources must satisfy all nine steps in sequence:
1. **Authenticate Actor**: Verify JWT signature, extract `actor_id` (`sub`).
2. **Establish Tenant**: Extract `tenant_id`, bind `SqlAlchemyUnitOfWork` to PostgreSQL RLS.
3. **Confirm Caregiver Role**: Assert `CareTeamRole.CAREGIVER` (or realm role `caregiver`) is present in `ctx.roles`.
4. **Resolve Relationship**: Query `CaregiverRelationshipRepository` for `(tenant_id, caregiver_user_id, patient_id)`.
5. **Confirm Status**: Assert relationship `status == CaregiverRelationshipStatus.VERIFIED`.
6. **Confirm Non-Expired**: Assert `expires_at IS NULL or expires_at > current_time`.
7. **Evaluate Operation Capability**: Assert requested operation is in the allowed Caregiver Capability Set.
8. **Confirm Resource Match**: Assert requested `patient_id` matches the relationship record.
9. **Authorize Execution**: Allow request to proceed to application use-case handler.

Any failure at steps 3–8 must **FAIL CLOSED (HTTP 403 Forbidden)**.

#### 3. Phase-1 Caregiver Capability Matrix

| Operation | Access | Rationale / Clinical Boundary |
| :--- | :---: | :--- |
| `READ_PATIENT_PROFILE` | **DENY** | Denied in Phase 1 unless minimal demographic profile is required |
| `READ_GLUCOSE_OBSERVATIONS` | **ALLOW** | Monitoring dependent's glycemic values |
| `CREATE_GLUCOSE_OBSERVATION` | **ALLOW** | Logging blood sugar on behalf of dependent |
| `READ_MEAL_OBSERVATIONS` | **ALLOW** | Monitoring dependent's dietary intake |
| `CREATE_MEAL_OBSERVATION` | **ALLOW** | Logging meals on behalf of dependent |
| `READ_MEDICATION_EVENTS` | **ALLOW** | Verifying medication adherence |
| `CREATE_MEDICATION_EVENT` | **ALLOW** | Logging medication administration on behalf of dependent |
| `READ_CARE_TASKS` | **ALLOW** | Viewing assigned care tasks |
| `COMPLETE_CARE_TASK` | **ALLOW** | Completing non-clinical care tasks (e.g., logging reminder) |

#### 4. Strictly Denied Caregiver Operations (Frozen Non-Goals)
The following operations are strictly forbidden to caregivers and must return HTTP 403:
- `WRITE_MEDICATION_PLAN` / `MODIFY_MEDICATION_PLAN`: Clinician authority only.
- `APPROVE_AI_ARTIFACT` / `REVIEW_AI_ARTIFACT`: Licensed clinician authority only.
- `CLINICAL_DIAGNOSIS` / `CLINICAL_DECISION_SUPPORT`: Medical practice violation.
- `ARBITRARY_PATIENT_SEARCH`: Privacy violation.
- `FACILITY_WIDE_PATIENT_ACCESS`: Privacy violation.
- `TENANT_WIDE_PATIENT_ACCESS`: Privacy violation.

Caregiver roles **never inherit** any clinician authority (`DOCTOR`, `NURSE`, `DIETITIAN`, `CARE_COORDINATOR`, `FIELD_HEALTH_WORKER`). If an operation is not explicitly listed as ALLOW, it defaults to **DENY**.

---

### CORRECTION 4: Clinician Facility Authorization & Stale JWT Mitigation

#### 1. The Stale JWT Facility Vulnerability
In distributed OIDC architectures, a clinician transferred or revoked from Facility A may continue to present a valid JWT bearing `facility_id: "Facility-A"` until the token reaches its natural expiration (e.g., 15–60 minutes). Relying solely on the JWT `facility_id` claim permits unauthorized clinical access during this vulnerability window.

#### 2. Server-Side CareTeamMember as Sole Authorization Authority
Clinical facility authorization is anchored exclusively in current database state:
```
JWT sub (actor_id)
   ↓
CareTeamMember lookup via CareTeamMemberRepository.get(user_id=actor_id)
   ↓
Assert CareTeamMember.active == True
   ↓
Extract current authoritative CareTeamMember.facility_id
   ↓
Compare with target Patient.facility_id
   ↓
Authorization Decision
```

The database `CareTeamMember` record is the sole authority for:
- Active vs. inactive clinician employment status.
- Current authorized `facility_id`.
- Verified clinical role (`CareTeamRole`).
- Statutory clinical capabilities (`can_author_medication`).

#### 3. Conflict Resolution: JWT vs. Server-Side Membership
The JWT `facility_id` claim is treated strictly as a **consistency hint**:
- If the JWT contains a `facility_id` and it **conflicts** with the server-side `CareTeamMember.facility_id`:  
  $$\text{JWT.facility\_id} \ne \text{CareTeamMember.facility\_id} \implies \mathbf{FAIL\ CLOSED\ (HTTP\ 403)}$$
- A clinician cannot use an outdated JWT to operate in an old facility, nor can they use a token minted for Facility A to access Facility B.
- If the clinician is marked `active = False` in `CareTeamMember`, access is immediately revoked regardless of token validity.
- Universal doctor access remains strictly barred: a doctor may only access patients enrolled in their currently assigned facility.

---

## 7. Canonical Gate 08 Authorization Model

The unified, frozen authorization model governing all actors in Gate 08 is rendered below:

```
                               JWT / Keycloak Token
                                        │
                                        ▼
                              AuthenticatedContext
                        (actor_id, tenant_id, roles)
                                        │
                                        ▼
                            PostgreSQL Tenant Boundary
                      (SqlAlchemyUnitOfWork + RLS set_config)
                                        │
                                        ▼
                                   Coarse RBAC
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             ▼                          ▼                          ▼
        [ PATIENT ]               [ CAREGIVER ]              [ CLINICIAN ]
             │                          │                          │
             ▼                          ▼                          ▼
   IdentityPatientMapping      CaregiverRelationship         CareTeamMember
   (user_id == actor_id)    (caregiver_user_id==actor_id)   (user_id == actor_id)
             │                          │                          │
             ▼                          ▼                          ▼
       Mapping Active?           Status == VERIFIED?         Member Active?
             │                   expires_at > now?                 │
             │                          │                          ▼
             ▼                          ▼                   Authoritative
        patient_id                  patient_id               facility_id
             │                          │                          │
             │                          │                          ▼
             │                          │                 Patient.facility_id
             │                          │                       Match?
             │                          │                          │
             └──────────────────────────┼──────────────────────────┘
                                        │
                                        ▼
                            Operation Policy Evaluation
                       (Caregiver Matrix / Clinician Rules)
                                        │
                                        ▼
                            Clinical Authority Guard
                       (MedicationPlan / AI Review Check)
                                        │
                                        ▼
                                    [ ALLOW ]
                                        │
                        (Any unresolved condition => DENY)
```

---

## 8. Preservation of Existing Clinical Authority

Gate 08 guarantees that no identity expansion weakens the clinical safety boundaries frozen in Gates 03–07:

### 8.1 MedicationPlan Authoring Authority
The three-layer defense for prescription directives remains intact:
1. **HTTP Layer**: Coarse RBAC verifies `Operation.WRITE_MEDICATION_PLANS`.
2. **Application Layer**: `CreateMedicationPlanHandler` verifies `CareTeamMember.role.can_author_medication`.
3. **Domain Layer**: `MedicationPlan.__post_init__` enforces that `prescribed_by_role` is in `{DOCTOR, NURSE, DIETITIAN}`. Patients, caregivers, AI models, and administrative staff can never author medication plans.

### 8.2 AI Artifact Review Authority
1. **HTTP Layer**: Guarded by `Operation.REVIEW_AI_ARTIFACT`.
2. **Application Layer**: `ReviewAIArtifactHandler` enforces `_LICENSED_ROLES = {DOCTOR, NURSE, DIETITIAN}`.
3. **Domain Layer**: `AIReviewArtifact` state machine allows review transitions only by licensed human clinicians. AI models never possess self-approval authority.

### 8.3 Patient Confirmation vs. Clinician Review Separation
Patient portion confirmation (`ConfirmMealObservation`, `PatientConfirmationState`) is an autonomous patient authority that confirms volumetric intake facts. It is strictly separate from clinician diagnostic review and is never collapsed into the AI artifact review state machine.

---

## 9. Proposed Contract Catalog (Gate 08 Scaffolding)

### 9.1 CaregiverRelationshipRepository Port
```python
class CaregiverRelationshipRepository(Protocol):
    def add(self, relationship: CaregiverRelationship) -> None: ...
    def get(self, relationship_id: UUID) -> CaregiverRelationship: ...
    def get_by_caregiver(
        self, caregiver_user_id: UUID
    ) -> list[CaregiverRelationship]: ...
    def get_by_patient(
        self, patient_id: UUID
    ) -> list[CaregiverRelationship]: ...
    def get_verified_for_patient(
        self, caregiver_user_id: UUID, patient_id: UUID
    ) -> CaregiverRelationship | None:
        """Fetch relationship where status == VERIFIED and unexpired."""
        ...
    def save(self, relationship: CaregiverRelationship) -> None: ...
```

### 9.2 IdentityPatientMappingRepository Port
```python
class IdentityPatientMappingRepository(Protocol):
    def add(self, mapping: IdentityPatientMapping) -> None: ...
    def get_by_user_id(self, user_id: UUID) -> IdentityPatientMapping | None: ...
    def get_by_patient_id(self, patient_id: UUID) -> IdentityPatientMapping | None: ...
    def deactivate(self, user_id: UUID) -> None: ...
```

### 9.3 UnitOfWork Protocol Extension
```python
class UnitOfWork(Protocol):
    # Existing Gate 04/07 attributes
    patients: PatientRepository
    care_team_members: CareTeamMemberRepository
    glucose_observations: GlucoseObservationRepository
    meal_observations: MealObservationRepository
    medication_plans: MedicationPlanRepository
    care_tasks: CareTaskRepository
    ai_artifacts: AIReviewArtifactRepository
    
    # Gate 08 Additions
    caregiver_relationships: CaregiverRelationshipRepository
    identity_mappings: IdentityPatientMappingRepository
    
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

---

## 10. Proposed Persistence & Database Schema (Alembic)

Both new tables are multi-tenant roots governed by PostgreSQL Row Level Security.

### 10.1 `caregiver_relationships` Table

```sql
CREATE TABLE caregiver_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    caregiver_user_id UUID NOT NULL,
    relationship_label VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    verified_at TIMESTAMPTZ NULL,
    revoked_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Row Level Security
ALTER TABLE caregiver_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE caregiver_relationships FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_caregiver_relationships ON caregiver_relationships
FOR ALL
USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

-- Prevent duplicate active/pending proxy links
CREATE UNIQUE INDEX uq_caregiver_rel_active ON caregiver_relationships(tenant_id, patient_id, caregiver_user_id)
WHERE status IN ('PENDING', 'VERIFIED');

CREATE INDEX ix_caregiver_rel_lookup ON caregiver_relationships(tenant_id, caregiver_user_id, status);
CREATE INDEX ix_caregiver_rel_patient ON caregiver_relationships(tenant_id, patient_id);
```

### 10.2 `identity_patient_mappings` Table

```sql
CREATE TABLE identity_patient_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Row Level Security
ALTER TABLE identity_patient_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity_patient_mappings FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_identity_patient_mappings ON identity_patient_mappings
FOR ALL
USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

-- Strict 1:1 Mapping per Tenant
CREATE UNIQUE INDEX uq_identity_mapping_user ON identity_patient_mappings(tenant_id, user_id)
WHERE active = TRUE;

CREATE UNIQUE INDEX uq_identity_mapping_patient ON identity_patient_mappings(tenant_id, patient_id)
WHERE active = TRUE;

CREATE INDEX ix_identity_mapping_lookup ON identity_patient_mappings(tenant_id, user_id);
```

---

## 11. Updated Threat Model

| Threat ID | Threat Description | Attack Vector | Gate 08A Mitigation |
| :--- | :--- | :--- | :--- |
| **T-01** | Stale JWT Facility Claim | Clinician transferred from Facility A to B uses unexpired JWT to access Facility A patients. | **Server-Side Authority & Fail-Closed**: Authorize against `CareTeamMember.facility_id`. If JWT `facility_id` mismatches database, fail closed (403). |
| **T-02** | Identity Mapping Administration Abuse | Admin user creates mapping and attempts to access patient clinical observations. | **Separation of Capabilities**: `MANAGE_IDENTITY_PATIENT_MAPPINGS` grants zero clinical data access. Clinical routes require active clinical membership. |
| **T-03** | Expired Caregiver Access Window | Caregiver accesses dependent records after court-ordered expiration date. | **Request-Time Check**: Application policy evaluates `expires_at > now` on every call. Fails closed without waiting for scheduler. |
| **T-04** | Caregiver Capability Creep | Caregiver attempts to modify medication plan or diagnose patient. | **Explicit Capability Matrix**: Operations outside the 8 permitted caregiver actions fail closed (403). |
| **T-05** | IDOR via Arbitrary `patient_id` | Patient calls `/api/v2/clinical/observations?patient_id={victim_id}`. | **Cryptographic Resolution**: Patient role parameter is resolved strictly from `IdentityPatientMapping(user_id=actor_id)`. Mismatches return 403. |
| **T-06** | Cross-Tenant Relationship Injection | Attacker links Tenant A caregiver to Tenant B patient. | **PostgreSQL RLS with CHECK**: Table RLS prevents inserting or querying relationships outside current transaction tenant context. |
| **T-07** | Concurrent Revocation Race | Caregiver accesses record during active revocation transaction. | **Revocation Fail-Closed & DB Transaction**: Status set to `REVOKED` in transaction. Query requires `status == 'VERIFIED'`. |

---

## 12. Updated Test Requirements (Gate 08 Verification Plan)

When Gate 08 implementation commences, the following test matrix must be executed and verified green:

### 12.1 Caregiver Lifecycle & Authorization Tests
- `test_caregiver_relationship_lifecycle_transitions`: Verify valid transitions (`PENDING → VERIFIED → REVOKED`, `VERIFIED → EXPIRED`) and assert that invalid transitions fail closed.
- `test_caregiver_re_revocation_fails_closed`: Assert invoking `revoke()` on an already revoked relationship raises `InvalidRelationship`.
- `test_caregiver_request_time_expiration_denies_without_scheduler`: Seed relationship with `expires_at` in the past and `status = 'VERIFIED'`; assert immediate 403 response.
- `test_caregiver_capability_matrix_enforcement`: Assert caregiver can read/log glucose, meals, and tasks, but receives 403 for medication plans and AI reviews.

### 12.2 Identity Mapping & Administrative Tests
- `test_identity_mapping_administrative_workflow_only`: Assert no self-service mapping endpoint exists; assert administrative endpoint requires `MANAGE_IDENTITY_PATIENT_MAPPINGS`.
- `test_identity_admin_cannot_access_clinical_data`: Assert that an administrator managing mappings receives 403 when requesting clinical observation feeds.
- `test_identity_mapping_strict_1_to_1_cardinality`: Assert attempting to map a second user to a patient or a second patient to a user raises 409 Conflict.

### 12.3 Clinician Facility Authority & Stale Claim Tests
- `test_clinician_access_authorized_via_server_care_team_member`: Verify clinician access matches current database facility assignment.
- `test_clinician_jwt_facility_conflict_fails_closed`: Present JWT with `facility_id: A` while `CareTeamMember.facility_id` is `B`; assert 403 Forbidden.
- `test_deactivated_clinician_denied_immediately`: Deactivate `CareTeamMember`; assert immediate 403 despite presenting a valid, unexpired clinician JWT.

---

## 13. Scope Boundaries & Non-Goals

### Gate 08 Scope (When Implementation Opens)
1. Application repository protocols (`CaregiverRelationshipRepository`, `IdentityPatientMappingRepository`).
2. Domain entity extension (`CaregiverRelationshipStatus` enum, transition guards).
3. ORM models and Alembic migrations with RLS policies and partial unique indexes.
4. `SqlAlchemyUnitOfWork` extension with the new repositories.
5. Server-side clinician facility lookup and conflict check.
6. Identity resolver and `RelationshipAuthorizationPolicy` with operation capability checks.
7. Administrative identity mapping routes and patient/caregiver-authorized clinical routes.

### Explicit Gate 08 Non-Goals
- ❌ **NO self-service identity mapping or SMS/phone linking**.
- ❌ **NO universal admin access to healthcare records**.
- ❌ **NO persistent `active` column in `CaregiverRelationship`**.
- ❌ **NO dependency on Gate 09 schedulers for expiration enforcement**.
- ❌ **NO caregiver medication planning or AI review authority**.
- ❌ **NO Redis idempotency, rate limiting, or AuditStore** (Deferred to Gate 09).
- ❌ **NO mobile or admin web frontend changes**.

---

## 14. Final Architectural Freeze Declaration

1. **Gate 08A Freeze Complete**: The four architectural corrections (Caregiver Lifecycle, Administrative Identity Mapping, Caregiver Capability Matrix, and Clinician Facility Authority) are formally frozen.
2. **Gate 07 Remains Sealed**: Commit `fc3e594` and tag `gate-07-http-security-complete` remain completely untouched and immutable.
3. **No Code Implementation**: No source code, tests, migrations, or database schemas have been modified.
4. **Gate 08 Implementation**: **NOT STARTED** (Awaiting formal stakeholder authorization).

---
*Document sealed on 2026-09-15. Gate 08A Contract and Identity Architecture Correction Freeze complete. Working tree clean.*
