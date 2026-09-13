# GATE 04 — Application Layer + Outbound Ports

**THALI × P.L.A.T.E. Production Program — Controlled Application-Layer
Extraction**

- **Status:** PASS
- **Type:** Application-layer orchestration + outbound-port contracts (pure;
  no infrastructure, no persistence, no framework ingestion)
- **Branch:** `feature/gate-04-application-layer`
- **Starting commit/tag:** `gate-03-domain-extraction-complete`
  (`d38373e61944cb6207c0356ada5f813c7153a15f`)

---

## 1. Gate objective

Implement the application layer on top of the pure Gate 03 domain contracts,
expressing **WHAT** the system needs to do through use-case orchestration and
outbound ports. Enforcement objectives: dependency inversion
(`interfaces → application → domain` and `infrastructure → application/domain`),
no infrastructure implementations, no framework imports, and preservation of
the frozen safety/authority/AI-review/information-asymmetry invariants.

## 2. Starting commit/tag

```
Tag:                 gate-03-domain-extraction-complete
Commit:              d38373e61944cb6207c0356ada5f813c7153a15f
Branch at start:     feature/gate-03-domain-models
Branch for Gate 04:  feature/gate-04-application-layer (created from tag)
```

Pre-execution baseline: `pytest tests -q` → **105 passed** (Gate 03 checkpoint).

## 3. Files created (39)

Backend — 30 files:

| Path | Justification |
| :--- | :--- |
| `backend/application/commands/complete_care_task.py` | CareTask completion command contract |
| `backend/application/commands/confirm_meal_observation.py` | Patient confirmation (replaces placeholder `confirm_meal_portion`) |
| `backend/application/commands/create_care_task.py` | CareTask creation command contract |
| `backend/application/commands/create_medication_plan.py` | Clinician-authority command (critical invariant) |
| `backend/application/commands/generate_ai_review_artifact.py` | AI draft-generation command |
| `backend/application/commands/record_medication_administration.py` | Patient adherence event (replaces placeholder `log_medication_admin`) |
| `backend/application/commands/review_ai_artifact.py` | Clinician review of pending AI artifact |
| `backend/application/ports/clock.py` | `Clock` outbound port (deterministic time) |
| `backend/application/ports/id_generation.py` | `IdGenerator` outbound port (deterministic ids) |
| `backend/application/ports/repositories.py` | Typed repository ports derived from Gate 03 entities |
| `backend/application/ports/unit_of_work.py` | `UnitOfWork` transaction-boundary port |
| `backend/application/dtos/results.py` | Command result DTOs (frozen, minimal) |
| `backend/application/dtos/patient_facing.py` | Patient information-boundary DTO |
| `backend/application/dtos/clinical.py` | Clinician-only DTO (separate type) |
| `backend/application/queries/get_patient_observation_feed.py` | Patient timeline query contract |
| `backend/application/queries/get_clinical_observation_feed.py` | Clinician timeline query contract |
| `backend/application/services/_transaction.py` | Single commit-or-rollback helper |
| `backend/application/services/ingest_glucose.py` | `IngestGlucoseReading` use case |
| `backend/application/services/link_patient_phone.py` | `LinkPatientPhone` use case |
| `backend/application/services/log_meal_draft.py` | `LogMealDraft` use case |
| `backend/application/services/confirm_meal_observation.py` | `ConfirmMealObservation` use case |
| `backend/application/services/record_medication_administration.py` | `RecordMedicationAdministration` use case |
| `backend/application/services/create_care_task.py` | `CreateCareTask` use case |
| `backend/application/services/complete_care_task.py` | `CompleteCareTask` use case |
| `backend/application/services/create_medication_plan.py` | `CreateMedicationPlan` use case (clinician-only) |
| `backend/application/services/generate_ai_artifact.py` | `GenerateAIReviewArtifact` use case |
| `backend/application/services/review_ai_artifact.py` | `ReviewAIArtifact` use case (licensed clinician only) |
| `backend/application/services/get_patient_observation_feed.py` | Patient feed query handler |
| `backend/application/services/get_clinical_observation_feed.py` | Clinician feed query handler |
| `backend/application/exceptions.py` | `ApplicationError` + `ReviewerNotAuthorized` (app-policy only) |

Test infrastructure — 9 files:

| Path | Justification |
| :--- | :--- |
| `tests/unit/application/fakes.py` | Deterministic in-memory fakes: Clock, IdGenerator, event publisher, AI generator, staged repositories, UnitOfWork |
| `tests/unit/application/conftest.py` | Seeded in-memory world + handler wiring |
| `tests/unit/application/test_commands.py` | Success orchestration, domain propagation, repository interaction, event publication (10 tests) |
| `tests/unit/application/test_unit_of_work.py` | Commit/rollback, no partial commits (5 tests) |
| `tests/unit/application/test_medication_authority.py` | Clinician-only plan creation; patient administration distinction (7 tests) |
| `tests/unit/application/test_ai_review_boundary.py` | AI artifact stays pending; AI cannot approve/action (8 tests) |
| `tests/unit/application/test_dto_boundaries.py` | Patient vs clinician DTO separation (6 tests) |
| `tests/unit/application/test_events_and_determinism.py` | Event provenance/correlation + deterministic time/ids (5 tests) |
| `tests/unit/architecture/test_import_boundaries.py` | Import/dependency/circular-import audit (8 tests) |

## 4. Files modified (11)

| Path | Justification |
| :--- | :--- |
| `backend/application/__init__.py` | Export subpackages; layer docstring |
| `backend/application/commands/__init__.py` | Export reconciled command set |
| `backend/application/commands/ingest_glucose_reading.py` | Strict required fields (`patient_id`, `value`, `taken_at`) + `correlation_id` |
| `backend/application/commands/link_patient_phone.py` | Strict required fields + `correlation_id` |
| `backend/application/commands/log_meal_draft.py` | Strict required fields + `portion` + `correlation_id` |
| `backend/application/dtos/__init__.py` | Export result + boundary DTOs |
| `backend/application/ports/__init__.py` | Export Gate 04 ports (+ retained deferred scaffolds) |
| `backend/application/ports/ai.py` | Provider-neutral `AIArtifactGenerator` / `ArtifactDraft` (replaces placeholder extraction engine) |
| `backend/application/ports/events.py` | `DomainEventPublisher` (canonical domain-event outbound port) |
| `backend/application/queries/__init__.py` | Export query contracts |
| `backend/application/services/__init__.py` | Export the 12 use-case handlers |

## 5. Files deleted (2)

| Path | Justification |
| :--- | :--- |
| `backend/application/commands/confirm_meal_portion.py` | Superseded by domain-vocabulary `confirm_meal_observation.py` |
| `backend/application/commands/log_medication_admin.py` | Superseded by `record_medication_administration.py` |

Retained (untouched, deferred): `commands/evaluate_escalations.py`,
`ports/notifications.py`, `ports/reporting.py`, `ports/storage.py`,
`queries/compute_window_metrics.py`, `queries/build_clinical_report_context.py`,
`queries/get_live_inbound.py` — approved Gate 03 scaffold contracts with
documented later-gate targets; no Gate 04 use case consumes them.

## 6. Application architecture

```
backend/application/
  commands/     frozen input contracts (required fields, domain VOs)
  queries/      read-side input contracts
  dtos/         results + patient-facing AND clinician-only boundary DTOs
  ports/        outbound contracts: Clock, IdGenerator, DomainEventPublisher,
                UnitOfWork, 7 repository ports, AIArtifactGenerator
                (+ retained deferred scaffold ports)
  services/     use-case handlers (orchestration)
  exceptions.py application-policy errors only (domain errors propagate)
```

Use cases depend only on `application.ports`, `application.commands/queries`,
`application.dtos`, and the `domain`. Every handler follows the same skeleton:

```
validate input shape (frozen command dataclass)
-> load domain entities through repository ports
-> invoke domain behaviour (domain invariants stay authoritative)
-> stage domain state through repository ports
-> publish canonical domain events through DomainEventPublisher
-> commit through UnitOfWork (rollback on any failure -> re-raise)
-> return a frozen result DTO
```

A single `_transaction.in_transaction` helper guarantees
**one commit / one rollback per use case** — never a partial commit.

## 7. Dependency direction

```
interfaces -> application -> domain
infrastructure -> application / domain
```

- `backend/domain` imports stdlib only (verified by static AST audit + grep).
- `backend/application` imports only `backend.domain` and its own
  subpackages; zero `backend.infrastructure` / `backend.interfaces` / `app`
  / framework / network imports.
- No circular dependencies (AST graph + live-import validation, 74 modules).

## 8. Ports created

| Port | Justification |
| :--- | :--- |
| `Clock` | deterministic current-time injection (no `datetime.now()` in use cases) |
| `IdGenerator` | deterministic identifier injection (no `uuid.uuid4()` in use cases) |
| `DomainEventPublisher` | canonical domain-event outbound publication |
| `UnitOfWork` | transaction boundary; repo access + `commit()` / `rollback()` |
| `PatientRepository` | LinkPatientPhone / data-origin verification |
| `CareTeamMemberRepository` | clinician-role sourcing (medication + AI review) |
| `GlucoseObservationRepository` | ingest + feeds |
| `MealObservationRepository` | draft/confirm + feeds |
| `MedicationPlanRepository` | create plan + administration check |
| `CareTaskRepository` | create/complete task |
| `AIReviewArtifactRepository` | generate/review AI artifacts |
| `AIArtifactGenerator` | provider-neutral AI port; returns **drafts**, never approvals |

Deliberately **not** declared: `CaregiverRelationshipRepository`,
`DocumentRepository` — no Gate 04 use case requires them ("define ports only
where orchestration requires them").

## 9. Use cases created (12)

Commands (10): `IngestGlucoseReading` · `LinkPatientPhone` · `LogMealDraft` ·
`ConfirmMealObservation` · `RecordMedicationAdministration` · `CreateCareTask` ·
`CompleteCareTask` · `CreateMedicationPlan` · `GenerateAIReviewArtifact` ·
`ReviewAIArtifact`.

Queries (2): `GetPatientObservationFeed` (patient-facing) ·
`GetClinicalObservationFeed` (clinician-only).

Deferred contracts (no handler in Gate 04): `EvaluateEscalations`,
`ComputeWindowMetrics`, `BuildClinicalReportContext`, `GetLiveInbound`.

## 10. DTO boundaries

- **Patient-facing** (`PatientObservationFeed`, list of domain
  `PatientFacingMealObservation` / `PatientFacingGlucoseObservation`):
  never contains `carbs_grams`, `glycemic_index`, or any clinical synthesis;
  verified structurally (dataclass fields) and on serialization.
- **Clinician-only** (`ClinicalObservationFeed`, `ClinicalMealRecord`,
  `ClinicalGlucoseRecord`): carries the analytical fields and is a
  **separate type**. No single universal DTO exists.

## 11. Transaction / UoW model

- `UnitOfWork` is an application **port** (no SQLAlchemy, no SQLite, no
  PostgreSQL).
- Repositories stage writes; `commit()` publishes them atomically,
  `rollback()` discards them. Fakes emulate this; in-memory tests verify
  zero partial commits when a failure occurs mid-use-case (after staged
  writes and after provider failure).

## 12. AI boundary

- Provider-neutral `AIArtifactGenerator.generate(...) -> ArtifactDraft`.
- `GenerateAIReviewArtifact` records the draft as a domain `AIReviewArtifact`
  and transitions it ONLY `GENERATED → PENDING_REVIEW` (a domain transition,
  not approval).
- `ReviewAIArtifact` (licensed clinical role: doctor/nurse/dietitian) drives
  `APPROVE / EDIT / REJECT` through the domain state machine.
- `ACTION / AUDIT` remain domain transitions exercised in later gates.
- No AI provider is called anywhere in Gate 04; tests use a deterministic
  fake.

## 13. Medication authority enforcement

- `CreateMedicationPlan` resolves the actor from the authoritative
  `CareTeamMember` record; the domain `MedicationPlan` construction enforces
  `CareTeamRole.can_author_medication` (doctor/nurse/dietitian). A non-clinician
  actor raises `UnauthorizedMedicationPlanMutation` and the transaction rolls
  back. A patient/caregiver id is not an accepted prescriber source.
- `RecordMedicationAdministration` is a distinct patient-side **adherence**
  operation: loads an existing active plan, never mutates it, and emits the
  canonical `MedicationAdministrationRecorded` event. Tests prove the two
  operations never conflate.

## 14. Patient/clinician information boundary

- Frozen asymmetry retained: patient-facing projections/DTOs exclude
  clinician-only glycemic/macronutrient analytics.
- Clinical feed returns the separate clinician DTO; tests assert the two types
  never collapse and patient serialization leaks nothing.

## 15. Test results

```
$ pytest tests -q
154 passed, 55 warnings in 2.66s

Baseline (before Gate 04): 105 passed  (Gate 03 checkpoint)
Gate 04 new:                49 passed  (baseline tests untouched)
Total:                      154 passed, 0 failures
```

Gate 04 breakdown: `test_commands` 10 · `test_unit_of_work` 5 ·
`test_medication_authority` 7 · `test_ai_review_boundary` 8 ·
`test_dto_boundaries` 6 · `test_events_and_determinism` 5 ·
`test_import_boundaries` 8.

Coverage of the mandated Gate 04 scenarios: success orchestration, domain
invariant propagation, repository interaction, event publication, UoW commit,
rollback on failure, deterministic time, deterministic identifiers,
clinician-only plan creation, patient administration distinction, AI artifact
stays pending, AI cannot approve/action, patient DTO has no clinical analytics,
event identity/provenance survives the flow, zero infrastructure imports, zero
legacy imports, no network-capable imports, correlation/idempotency
propagation.

## 16. Import / dependency audit

Static AST audit (`tests/unit/architecture/test_import_boundaries.py`):

- `domain` → stdlib only: **0 forbidden imports**
- `application` → domain + application-local only: **0 infrastructure /
  interfaces / legacy `app` / framework / network imports**
- Circular imports over `backend.application` + `backend.domain` graph:
  **none** (also verified by a live `importlib` pass over **74 modules**)
- No `httpx` / `requests` / `urllib` / `socket` / `http.client` anywhere in
  the audited layers (no network calls)

## 17. Legacy preservation verification

- `git status` (before commit): no changes under `app/**`, `tests/`,
  `tests/conftest.py`, `config/`, `requirements.txt`, `backend/domain`,
  `backend/infrastructure`, `backend/interfaces`.
- Verified live:
  ```
  from app.core.datamodel import Store   -> constructs + opens legacy schema
  from app.config import Settings        -> OK
  from app.server.main import create_app -> returns FastAPI app
  ```
- Baseline test files untouched (`tests/test_linking.py`,
  `tests/test_pipeline.py`, `tests/conftest.py`, `tests/unit/domain/*`,
  `tests/unit/config/*`).

## 18. Known limitations

1. `RecordMedicationAdministration` persists no first-class domain entity —
   Gate 03 defines the `MedicationAdministrationRecorded` event but no
   administration entity; the administration fact is emitted as the canonical
   event. A first-class record/entity + repository is a later-gate item.
2. `LinkPatientPhone`, `CreateMedicationPlan`, and `CompleteCareTask` have no
   canonical Gate 03 domain event for their outcome; they publish only when a
   domain event contract exists (no event mechanism invented here).
3. `CareTask.complete()` stamps `completed_at` inside the frozen domain entity
   (`datetime.utcnow()`); the handler reports that value while the use case's
   own event timestamp comes from the injected `Clock`.
4. Reviewer-authorization for AI artifact review (`ReviewerNotAuthorized`) is
   an application-policy guard until the domain/identity gate formalizes RBAC.
5. `GetClinicalObservationFeed` is clinician-shaped but interface-level RBAC
   enforcement is deferred to the interfaces/identity gate.
6. `EvaluateEscalations`, `ComputeWindowMetrics`, `BuildClinicalReportContext`,
   `GetLiveInbound` remain contract-only until their owning gates.
7. Notifications/reporting/object-storage ports are retained approved scaffold
   boundaries with no Gate 04 consumer.

## 19. Explicitly deferred infrastructure

| Item | Status |
| :--- | :--- |
| PostgreSQL / SQLAlchemy persistence | NOT IMPLEMENTED — 0 migrations, no connection |
| Alembic | NOT IMPLEMENTED |
| Redis | NOT IMPLEMENTED |
| S3 / object storage | NOT IMPLEMENTED (port boundary only) |
| Keycloak / OIDC / OAuth | NOT IMPLEMENTED |
| FastAPI endpoints (v2) | NOT IMPLEMENTED |
| WhatsApp Cloud / channel SDK | NOT IMPLEMENTED |
| Gemini / OpenAI provider SDK | NOT IMPLEMENTED (deterministic fake AI in tests) |
| Mobile / admin / clinical screens | NOT IMPLEMENTED |
| Legacy traffic redirection / legacy wrapping | NOT ACTIVATED (compatibility boundary unchanged) |

## 20. Exit criteria

| Criterion | Result |
| :--- | :--- |
| 105 baseline tests still pass | PASS |
| New Gate 04 tests (≥ mandated scenarios) | PASS (49 tests) |
| Application imports only domain + application-local | PASS (AST audit) |
| Domain purity (stdlib only) | PASS |
| Zero infrastructure/legacy/network coupling | PASS |
| No circular imports | PASS |
| Medication authority unambiguous | PASS (domain + application tests) |
| Patient DTO never exposes clinical analytics | PASS |
| No database connection / no migrations / no secrets | PASS |
| Legacy `app/**` untouched | PASS |

## 21. Commit hash

The Gate 04 checkpoint is pinned by the annotated tag
`gate-04-application-layer-complete` on branch
`feature/gate-04-application-layer`. Exact SHA is recorded in the tag object
and verified by `git rev-parse gate-04-application-layer-complete` at
checkpoint time.

Commit message: `feat(application): establish application use cases and
outbound ports`.

## 22. Gate tag

```
gate-04-application-layer-complete
```

---

## Failure-safety report

| Check | Result |
| :--- | :--- |
| Baseline tests before Gate 04 | 105 passed |
| Baseline tests after Gate 04 | 105 passed (unchanged) |
| Baseline tests edited | none |
| Legacy `app/**` modified/deleted | none |
| Database modified / migration | none |
| Dependency added | 0 |
| Application → infrastructure/legacy/network import | none (audit) |
| Domain purity violation | none |
| Circular import | none |
| Secrets committed | none |
| Working tree at checkpoint | clean |