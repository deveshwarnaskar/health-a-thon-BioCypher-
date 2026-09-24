# GATE 05 — INFRASTRUCTURE ADAPTERS

**THALI × P.L.A.T.E. Production Program — Infrastructure Layer & Outbound Adapters**

- **Status:** PASS
- **Type:** Concrete persistence & infrastructure adapters implementing Gate 04 application ports
- **Branch:** `feature/gate-05-infrastructure-adapters`
- **Starting commit:** `bb04699a839ff5cf8061b4f9f537d5a0fed4ab28`
- **Starting tag:** `gate-04-application-layer-complete`
- **Final commit:** `b7631da81560cf887e32f52b49d49054b7997813`
- **Final tag:** `gate-05-infrastructure-adapters-complete`

---

## 1. Objective

Provide concrete infrastructure implementations for the outbound application ports established in Gate 04, establishing:
- Multi-tenant relational persistence with PostgreSQL & SQLAlchemy 2.x
- Alembic database migration foundation with automatic upgrade/downgrade validation
- Transactional `UnitOfWork` with strict commit/rollback boundaries and no partial commits
- Transactional Outbox for canonical domain event persistence in the same transaction
- Concrete repositories for all 7 Gate 04 aggregates enforcing tenant boundaries
- PostgreSQL database-level Row Level Security (RLS) enforcement
- Object storage adapter (`S3ObjectStorage`) for clinical PDFs/images with key sanitization
- Redis caching and coordination adapter (`RedisCacheAdapter`) with TTL and in-memory fallback
- Keycloak identity foundation (`KeycloakTokenValidator`) with offline claim validation
- Provider-neutral AI draft generator (`ProviderNeutralAIAdapter`) preserving human clinical review
- Privacy-preserving structured logging (`InfrastructureLogger`) with strict PHI/PII redaction
- Preservation of inward dependency direction (`infrastructure -> application -> domain`), domain purity, and 100% baseline test integrity.

---

## 2. Starting Commit and Tag

```
Starting Tag:    gate-04-application-layer-complete
Starting Commit: bb04699a839ff5cf8061b4f9f537d5a0fed4ab28
Branch:          feature/gate-05-infrastructure-adapters
Baseline Tests:  154 passed (Gate 00: 57, Gate 03: 45, Gate 04: 52)
```

---

## 3. Infrastructure Architecture

The implementation strictly preserves the Hexagonal / Clean Architecture dependency inversion boundary:

```
    ┌─────────────────────────────────────────────────────────┐
    │                      INTERFACES                         │
    │         (CLI, HTTP routers - deferred to Gate 06)       │
    └────────────────────────────┬────────────────────────────┘
                                 │ depends inward
                                 ▼
    ┌─────────────────────────────────────────────────────────┐
    │                      APPLICATION                        │
    │         Use Cases, Orchestration, Outbound Ports        │
    │     (UnitOfWork, Repositories, DomainEventPublisher)    │
    └────────────────────────────┬────────────────────────────┘
                                 │ depends inward
                                 ▼
    ┌─────────────────────────────────────────────────────────┐
    │                        DOMAIN                           │
    │       Pure Entities, Value Objects, Domain Events       │
    │           (Stdlib only; Zero external frameworks)       │
    └─────────────────────────────────────────────────────────┘
                                 ▲
                                 │ implements ports
    ┌────────────────────────────┴────────────────────────────┐
    │                    INFRASTRUCTURE                       │
    │                                                         │
    │  PostgreSQL / SQLAlchemy 2.x  │ Transactional Outbox   │
    │  Alembic Migrations & RLS     │ S3 Object Storage      │
    │  SqlAlchemyUnitOfWork         │ Redis Cache Adapter    │
    │  Keycloak Identity Client     │ Provider-Neutral AI    │
    │  Structured Privacy Logger    │ SystemClock & UUID-Gen │
    └─────────────────────────────────────────────────────────┘
```

**Boundary Rules Enforced:**
- `backend/domain`: imports stdlib only (0 external dependencies, 0 ORM models).
- `backend/application`: imports `backend/domain` and application-local modules only.
- `backend/infrastructure`: imports `backend/application` and `backend/domain`.
- Repositories return pure domain entities, never raw SQLAlchemy models (`Mapped[]`).

---

## 4. Port-to-Adapter Matrix

| Application Port | Infrastructure Adapter | Technology / Mechanism | Gate 05 Status |
| :--- | :--- | :--- | :--- |
| `UnitOfWork` | `SqlAlchemyUnitOfWork` | SQLAlchemy 2.x Session transaction boundary | IMPLEMENTED |
| `PatientRepository` | `SqlAlchemyPatientRepository` | SQLAlchemy 2.x + PostgreSQL / SQLite | IMPLEMENTED |
| `CareTeamMemberRepository` | `SqlAlchemyCareTeamMemberRepository` | SQLAlchemy 2.x + PostgreSQL / SQLite | IMPLEMENTED |
| `GlucoseObservationRepository` | `SqlAlchemyGlucoseObservationRepository` | SQLAlchemy 2.x + PostgreSQL / SQLite | IMPLEMENTED |
| `MealObservationRepository` | `SqlAlchemyMealObservationRepository` | SQLAlchemy 2.x + PostgreSQL / SQLite | IMPLEMENTED |
| `MedicationPlanRepository` | `SqlAlchemyMedicationPlanRepository` | SQLAlchemy 2.x + PostgreSQL / SQLite | IMPLEMENTED |
| `CareTaskRepository` | `SqlAlchemyCareTaskRepository` | SQLAlchemy 2.x + PostgreSQL / SQLite | IMPLEMENTED |
| `AIReviewArtifactRepository` | `SqlAlchemyAIReviewArtifactRepository` | SQLAlchemy 2.x + PostgreSQL / SQLite | IMPLEMENTED |
| `DomainEventPublisher` | `SqlAlchemyOutboxDomainEventPublisher` | PostgreSQL Outbox table in same transaction | IMPLEMENTED |
| `Clock` | `SystemClock` | Python standard `datetime.now(timezone.utc)` | IMPLEMENTED |
| `IdGenerator` | `Uuid4IdGenerator` | Python standard `uuid.uuid4()` | IMPLEMENTED |
| `IObjectStorage` | `S3ObjectStorage` | S3-compatible API (boto3 + in-memory fallback) | IMPLEMENTED |
| `AIArtifactGenerator` | `ProviderNeutralAIAdapter` | Provider-neutral draft synthesis (draft only) | IMPLEMENTED |
| Caching Port | `RedisCacheAdapter` | Redis client with connection pool & fallback | IMPLEMENTED |
| Identity Port | `KeycloakTokenValidator` | Keycloak JWT claims & issuer validator | IMPLEMENTED |

---

## 5. PostgreSQL & SQLAlchemy Persistence

### 5.1 Tables and Relational Schema

1. `organizations`: Root multi-tenant entity (`id`, `name`, `slug`, `active`, `created_at`).
2. `facilities`: Physical clinical facilities under an organization (`id`, `tenant_id`, `name`, `active`, `created_at`).
3. `patients`: Patient profile (`id`, `tenant_id`, `facility_id`, `uh_id`, `name`, `phone`, `active`, `created_at`).
4. `care_team_members`: Clinicians and coordinators (`id`, `tenant_id`, `user_id`, `facility_id`, `role`, `display_name`, `active`, `created_at`).
5. `glucose_observations`: Glucose readings (`id`, `tenant_id`, `patient_id`, `taken_at`, `value_mg_dl`, `tag`, `confirmation`, `confirmed_by`, `created_at`).
6. `meal_observations`: Meal records with volumetric katori and clinical analytics (`id`, `tenant_id`, `patient_id`, `recorded_at`, `description`, `portion_food_key`, `portion_volume_ml`, `portion_quantity`, `carbs_grams`, `glycemic_index`, `confirmation`, `confirmed_by`, `created_at`).
7. `medication_plans`: Clinician-authored plans (`id`, `tenant_id`, `patient_id`, `prescribed_by_user_id`, `prescribed_by_role`, `medication`, `instruction`, `active`, `created_at`).
8. `care_tasks`: Care team workflow tasks (`id`, `tenant_id`, `patient_id`, `assigned_to_user_id`, `description`, `status`, `created_at`, `completed_at`).
9. `ai_review_artifacts`: AI extractions under human review (`id`, `tenant_id`, `patient_id`, `artifact_kind`, `authority`, `state`, `generated_by`, `summary`, `reviewed_by_user_id`, `created_at`).
10. `domain_event_outbox`: Transactional outbox for domain events (`event_id`, `tenant_id`, `event_type`, `occurred_at`, `patient_id`, `correlation_id`, `payload`, `published_at`).

### 5.2 Indexing Decisions

- **Multi-tenant Compound Indexes**:
  - `ix_patients_tenant_uh_id`: `(tenant_id, uh_id)`
  - `ix_patients_tenant_phone`: `(tenant_id, phone)`
  - `ix_care_team_members_tenant_user`: `(tenant_id, user_id)`
  - `ix_glucose_obs_tenant_patient_taken`: `(tenant_id, patient_id, taken_at)`
  - `ix_meal_obs_tenant_patient_recorded`: `(tenant_id, patient_id, recorded_at)`
  - `ix_medication_plans_tenant_patient`: `(tenant_id, patient_id)`
  - `ix_care_tasks_tenant_patient`: `(tenant_id, patient_id)`
  - `ix_care_tasks_tenant_assigned`: `(tenant_id, assigned_to_user_id)`
  - `ix_ai_artifacts_tenant_patient`: `(tenant_id, patient_id)`
  - `ix_ai_artifacts_tenant_state`: `(tenant_id, state)`
- **Outbox Index**:
  - `ix_outbox_unpublished`: `(event_type, published_at)` for fast polling of unpublished events.

---

## 6. SQLAlchemy Mapping Strategy

Explicit bidirectional mapping between domain entities and database models is encapsulated in `backend/infrastructure/persistence/mappings/mappers.py`:
- Value Objects are reconstructed with strict domain validation:
  - `UHID(model.uh_id)`
  - `PhoneNumber(model.phone)`
  - `GlucoseValue(model.value_mg_dl)`
  - `ReadingTag(model.tag)`
  - `MealPortion(food_key, KatoriVolume(volume_ml), quantity)`
- Enums are strictly mapped to domain types: `CareTeamRole`, `CareTaskStatus`, `PatientConfirmationState`, `ReviewAuthority`, `ReviewState`.
- Domain entities never inherit from SQLAlchemy `Base`.
- Repository methods return reconstructed domain entities; ORM objects never escape the repository boundary.

---

## 7. Alembic Migrations

- Initial migration: `backend/infrastructure/persistence/alembic/versions/0001_initial_schema.py`.
- Automated test coverage in `tests/integration/test_alembic_migrations.py`:
  - Verified upgrade from empty database to `head` on SQLite and PostgreSQL.
  - Verified downgrade from `head` back to `base`.
  - Schema creation is 100% managed by Alembic; no schema creation hidden inside application startup.

---

## 8. Unit of Work & Transactional Outbox

### 8.1 Unit of Work (`SqlAlchemyUnitOfWork`)
- Implements `UnitOfWork` protocol from `backend/application/ports/unit_of_work.py`.
- Coordinates all 7 repositories under an explicit transaction boundary.
- `commit()`: executes session commit.
- `rollback()`: executes session rollback.
- Exception safety: any unhandled exception in `in_transaction` triggers `rollback()` and leaves zero partial state.
- Supports both context manager (`with uow:`) and direct method orchestration.

### 8.2 Transactional Outbox (`SqlAlchemyOutboxDomainEventPublisher`)
- Implements `DomainEventPublisher` protocol from `backend/application/ports/events.py`.
- Appends domain events to `DomainEventOutboxModel` within the same SQLAlchemy session.
- Committing the UoW commits both the aggregate state change and the domain event record atomically.
- Rolling back the UoW rolls back the event record, eliminating phantom event risks.

---

## 9. Multi-Tenancy & PostgreSQL Row Level Security (RLS)

- **Repository Level**: Every repository requires `tenant_id: UUID` at instantiation. Queries filter on `Model.tenant_id == self.tenant_id`. Accessing or mutating another tenant's entity raises `EntityNotFound`. Passing `None` raises `ValueError` (cannot silently ignore tenant context).
- **PostgreSQL Database Level (RLS)**:
  - Enabled on all tenant tables: `patients`, `care_team_members`, `glucose_observations`, `meal_observations`, `medication_plans`, `care_tasks`, `ai_review_artifacts`, `domain_event_outbox`.
  - `FORCE ROW LEVEL SECURITY` enforced so policies apply even to table owners.
  - Policy:
    ```sql
    CREATE POLICY tenant_isolation_<table_name> ON <table_name>
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    ```
  - Safe fail-closed design: when `app.current_tenant_id` is empty, zero rows are returned.
  - Session parameterization: `SELECT set_config('app.current_tenant_id', :tid, true)` parameterized to prevent SQL injection.
  - Verified by integration tests with a non-superuser database role.

---

## 10. Secondary Adapters

### 10.1 S3 Object Storage (`S3ObjectStorage`)
- Implements `IObjectStorage` (`put`, `get`).
- Parameterized configuration (bucket, endpoint_url, region, credentials).
- Rejects path traversal (`..`) and empty keys.
- Operates in-memory when external object storage credentials are not provided.

### 10.2 Redis Cache (`RedisCacheAdapter`)
- Connection pool with timeout configuration.
- Methods: `get`, `set` (with TTL), `delete`, `ping`.
- In-memory fallback with TTL expiry for offline environments.
- Ready for Gate 06 rate limiting and ephemeral session caching.

### 10.3 Identity Foundation (`KeycloakTokenValidator`)
- Validates token format, expiration, issuer, and extracts claims (`user_id`, `roles`, `tenant_id`).
- No FastAPI middleware or endpoints in Gate 05 (deferred to Gate 06).

### 10.4 AI Draft Generator (`ProviderNeutralAIAdapter`)
- Implements `AIArtifactGenerator`.
- Produces unapproved `ArtifactDraft` instances only.
- Does not approve, action, or modify medication (strictly preserves clinical review invariants).

### 10.5 Privacy-Preserving Logging (`InfrastructureLogger`)
- Masks credentials (`password`, `token`, `secret`, `api_key`).
- Redacts PHI/PII (`phone`, `patient_name`, `uh_id`).
- Redacts clinical details from raw infrastructure logs (`carbs_grams`, `glycemic_index`, `medication`).

---

## 11. Legacy Preservation

- `app/**`: UNTOUCHED.
- `tests/test_linking.py`: UNTOUCHED (16 tests pass).
- `tests/test_pipeline.py`: UNTOUCHED (41 tests pass).
- `tests/conftest.py`: UNTOUCHED.
- Legacy SQLite databases (`aahaar.db`, `aahaar-demo.db`, WAL/SHM): UNTOUCHED.
- Legacy imports and app factory verified live (`Store`, `Settings`, `create_app`).

---

## 12. Security & Verification Audit

- **Secrets in Git**: None. All credentials configurable via environment.
- **`.env.example`**: Created in repository root with safe placeholders only.
- **SQL Injection**: None. 100% parameterized queries via SQLAlchemy 2.0 ORM and `set_config` bind parameters.
- **ORM Leakage**: None. Repositories return pure domain entities.
- **Circular Imports**: 0 circular imports across backend.
- **Import Boundaries**: Verified by static AST audit in `test_import_boundaries.py` (8/8 pass).

---

## 13. Test Results

```
============================== 209 passed in 4.52s ===============================
```

### Breakdown:
- **Gate 00 Baseline**: 57 passed (16 linking, 41 pipeline)
- **Gate 03 Domain**: 45 passed (pure domain entities & value objects)
- **Gate 04 Application**: 52 passed (use cases, UoW fakes, DTO boundaries, import boundaries)
- **Gate 05 Infrastructure Unit**: 52 passed
  - `test_sqlalchemy_mappings.py`: 7 passed
  - `test_sqlalchemy_repositories.py`: 7 passed
  - `test_tenant_isolation.py`: 8 passed
  - `test_sqlalchemy_unit_of_work.py`: 5 passed
  - `test_outbox_publisher.py`: 2 passed
  - `test_storage_adapter.py`: 5 passed
  - `test_redis_cache_adapter.py`: 5 passed
  - `test_identity_client.py`: 4 passed
  - `test_ai_adapter.py`: 2 passed
  - `test_observability_logging.py`: 3 passed
  - `test_database_config.py`: 3 passed
- **Gate 05 Integration**: 3 passed
  - `test_alembic_migrations.py`: 2 passed (SQLite & PostgreSQL upgrade/downgrade)
  - `test_postgres_repositories.py`: 1 passed (PostgreSQL repository CRUD & RLS isolation)
- **Total Failures**: 0

---

## 14. Deferred Work

The following items remain strictly deferred to subsequent gates:
- FastAPI v2 HTTP route implementations (Gate 06).
- Keycloak OAuth2 / OIDC authentication middleware (Gate 06).
- WhatsApp Cloud API webhook receiver and HMAC verification (Gate 06).
- SQLite-to-PostgreSQL production data migration (Dedicated migration gate).
- React Native mobile application and Web admin UI (Mobile/UI gates).

---

## 15. Gate Checkpoint Summary

- **Branch:** `feature/gate-05-infrastructure-adapters`
- **Starting Gate 04 SHA:** `bb04699a839ff5cf8061b4f9f537d5a0fed4ab28`
- **Annotated Tag:** `gate-05-infrastructure-adapters-complete`
