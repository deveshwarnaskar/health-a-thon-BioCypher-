# GATE 03 — Configuration & Pure Domain Extraction

**THALI × P.L.A.T.E. Production Program — Controlled Domain Extraction**

- **Status:** PASS (pending final gate report)
- **Type:** Pure-domain contract extraction + config boundary (no runtime
  behavior change, no DB migration, no feature work)
- **Branch:** `feature/gate-03-domain-models`
- **Executed against:** verified Aahaar baseline (Gate 00 verified, Gate 02B
  scaffolded, 57 tests)

---

## MANDATORY 26-POINT HORIZON (each item explicitly ENUMERATED below)

> Every item is either **`[IMPLEMENTED]`** or **`[NOT IMPLEMENTED — EXPLICITLY
> DEFERRED/EXCLUDED]`**. Nothing is left implied.

### 1. Project & gate identity
`[IMPLEMENTED]` THALI × P.L.A.T.E., GATE 03 Configuration & Pure Domain
Extraction. Executed on `feature/gate-03-domain-models` against verified
Gate 00/02B checkpoint (HEAD before this gate: `6bd6f33`,
`gate-02b-scaffolding-complete`, baseline `0d4613c`/`baseline-gate-00`).

### 2. Scope & acceptance criteria
`[IMPLEMENTED]` Extract pure domain vocabulary into `backend/domain/` and
establish a `config/` application-settings boundary. Acceptance = every
lightweight decision below demonstrably satisfied, baseline suite stays green,
legacy `app/**` remains the single operational implementation, no secrets.

### 3. Branch & baseline evidence
`[IMPLEMENTED]` Branch `feature/gate-03-domain-models` created from `master`
at `6bd6f33`; checked out before any change. Pre-execution baseline:
`pytest tests -q` → **57 passed** (3.23s).

### 4. Files CREATED (+ justification each)
`[IMPLEMENTED]` — 24 files created:

| Path | Justification |
| :--- | :--- |
| `backend/domain/value_objects/glucose.py` | `GlucoseValue` (20–600 mg/dL invariant) + `GlucoseMeasurement` |
| `backend/domain/value_objects/katori_volume.py` | `KatoriVolume` {150,220,350} ml canonical portions |
| `backend/domain/value_objects/confirmation.py` | `PatientConfirmationState` PENDING/CONFIRMED/CORRECTED/REJECTED |
| `backend/domain/entities/patient.py` | Patient aggregate identity |
| `backend/domain/entities/care_team_member.py` | `CareTeamRole` + `can_author_medication` authority |
| `backend/domain/entities/meal_observation.py` | Meal record + patient-facing projection source |
| `backend/domain/entities/glucose_observation.py` | Glucose record (patient-confirmation authority) |
| `backend/domain/entities/care_task.py` | Task entity |
| `backend/domain/entities/document_reference.py` | Document reference entity |
| `backend/domain/entities/ai_artifact.py` | `AIReviewArtifact` + `ReviewState` machine + `ReviewAuthority` |
| `backend/domain/entities/projections.py` | Patient-facing projections (information asymmetry) |
| `backend/domain/events/clinical.py` | 8 concrete clinical events |
| `config/settings.py` | pydantic-settings `Settings` (nested config, `THALI_` peer) |
| `config/__init__.py` | Re-export |
| `config/example.env` | Documented env example (no secrets) |
| `tests/unit/config/test_settings.py` | Config defaults/nesting/secret-free tests |
| `tests/unit/domain/test_glucose_value.py` | Glucose boundary invariants |
| `tests/unit/domain/test_katori_volume.py` | Katori volume invariants |
| `tests/unit/domain/test_phone_number.py` | Phone normalize/validate/mask |
| `tests/unit/domain/test_patient_facing_projection.py` | Information-asymmetry safety |
| `tests/unit/domain/test_medication_plan.py` | Medication clinician authority |
| `tests/unit/domain/test_ai_review_artifact.py` | AI review state machine |
| `tests/unit/domain/test_domain_event.py` | Domain event contract |
| `docs/migration/GATE_03_DOMAIN_EXTRACTION.md` | This gate checkpoint document (26-point horizon) |

New directories: `config/` became a package; `tests/unit/config/`,
`tests/unit/domain/` created. (`medication_plan.py` and `caregiver_relationship.py`
were rewritten in place — they are counted under Modified, not Created.)

### 5. Files MODIFIED (+ justification each)
`[IMPLEMENTED]` — 19 files modified:

| Path | Justification |
| :--- | :--- |
| `backend/domain/exceptions/__init__.py` | Full `DomainError` hierarchy (AppError was missing, split properly-valued errors, invalid transition, relationship, medication authority) |
| `backend/domain/value_objects/__init__.py` | Re-exports updated (removed `glucose_measurement`) |
| `backend/domain/value_objects/meal_portion.py` | Use `KatoriVolume` instead of raw int |
| `backend/domain/value_objects/phone_number.py` | Normalize/validate/mask + remove un-derivable `country_code` |
| `backend/domain/value_objects/uhid.py` | Documented pattern validation |
| `backend/domain/value_objects/time_window.py` | `start <= end` invariant verified |
| `backend/domain/entities/__init__.py` | Removed 6 placeholder exports, added real entities |
| `backend/domain/entities/medication_plan.py` | Real clinician-authority logic replacing frozen placeholder |
| `backend/domain/entities/caregiver_relationship.py` | Real relationship logic replacing frozen placeholder |
| `backend/domain/events/base.py` | Non-empty `event_type` invariant + identity/provenance/correlation |
| `backend/domain/events/__init__.py` | Re-export concrete events |
| `backend/domain/repositories/__init__.py` | Typed `Repository(Protocol, Generic[T])` contract |
| `backend/application/commands/ingest_glucose_reading.py` | Uses `GlucoseValue` |
| `backend/application/commands/log_meal_draft.py` | `patient_id` (was `patient_profile_id`) |
| `backend/application/commands/link_patient_phone.py` | `patient_id` (was `patient_profile_id`) |
| `backend/application/queries/compute_window_metrics.py` | `patient_id` alignment |
| `backend/application/queries/build_clinical_report_context.py` | `patient_id` alignment |
| `config/README.md` | Documented real config boundary |
| `requirements.txt` | Added `pydantic-settings>=2.4` (see item 7) |

No changes to `app/**`, baseline tests, or `pytest.ini`.

### 6. Files DELETED (+ justification each)
`[IMPLEMENTED]` — 7 placeholder modules removed (merging onto real contracts):

| Path | Justification |
| :--- | :--- |
| `backend/domain/entities/user.py` | Placeholder scaffold; real patient identity lives in `patient.py` + legacy `app.core.datamodel` |
| `backend/domain/entities/organization.py` | Placeholder; OBSERVABLE existence is `[NOT IMPLEMENTED — DEFERRED]` (see item 20) |
| `backend/domain/entities/facility.py` | Placeholder; OBSERVABLE existence is `[NOT IMPLEMENTED — DEFERRED]` |
| `backend/domain/entities/care_plan.py` | Placeholder; superseded by `medication_plan.py` + `care_task.py` |
| `backend/domain/entities/care_team_membership.py` | Merged into `care_team_member.py` role model |
| `backend/domain/entities/patient_profile.py` | Placeholder; renamed/merged into `patient.py` |
| `backend/domain/value_objects/glucose_measurement.py` | Superseded by `glucose.py` (`GlucoseValue` + `GlucoseMeasurement`) |

### 7. Dependencies ADDED (+ justification)
`[IMPLEMENTED]` — `pydantic-settings 2.15.0` installed into `.venv` and recorded
in `requirements.txt` as `pydantic-settings>=2.4`. Justification: the `config/`
application-settings boundary (Gate 03 scope) requires env-driven nested
settings validation; pydantic-settings is the sanctioned tool. `python-dotenv`
arrives as a transitive dependency. **No other dependency** added.

### 8. Migrations executed
`[NOT IMPLEMENTED — EXPLICITLY DEFERRED]` — **0 migrations executed.** No
PostgreSQL/SQLAlchemy/Alembic. Legacy `aahaar.db`, `aahaar.db-wal`, `aahaar.db-shm`
untouched. SQLite path held by `app.core.datamodel.Store` unchanged.

### 9. Domain purity invariant (backend/domain imports stdlib only)
`[IMPLEMENTED]` — Gated by grep audit (see item 22): no fastapi / sqlalchemy /
redis / boto3 / psycopg / sqlite3 / httpx / requests / google / openai /
pydantic / os / sys / pathlib / app / outer-layer imports anywhere under
`backend/domain/`. Value objects, entities, events, exceptions, repositories are
stdlib-only (dataclasses, enum, typing, datetime, uuid).

### 10. Information-asymmetry invariant (patient-facing projection)
`[IMPLEMENTED]` — `PatientFacingMealObservation`/`PatientFacingGlucoseObservation`
exclude `carbs_grams` and `glycemic_index`. Clinician-only analytical fields
remain on the clinical entities only. Proven by
`tests/unit/domain/test_patient_facing_projection.py`.

### 11. Review-state machines
`[IMPLEMENTED]` —
`ReviewState`: `GENERATED → PENDING_REVIEW → {APPROVED, EDITED, REJECTED} → ACTIONED → AUDITED`;
`ReviewAuthority`: `CLINICIAN_REVIEW` vs `PATIENT_CONFIRMATION` are distinct
enums — never collapsed. `PatientConfirmationState` separate. Illegal transitions
raise `InvalidStateTransition`. Proven by `test_ai_review_artifact.py`.

### 12. Medication-plan clinician authority
`[IMPLEMENTED]` — `MedicationPlan` can only be authored and mutated by
`CareTeamRole.DOCTOR | NURSE | DIETITIAN` (`can_author_medication`). All other
roles raise `UnauthorizedMedicationPlanMutation`. Proven by
`test_medication_plan.py`.

### 13. Glucose / measurement safety invariants
`[IMPLEMENTED]` — `GlucoseValue` clamps to **20–600 mg/dL** inclusive; below/above
and non-integer rejected with `InvalidGlucoseValue`. `KatoriVolume` restricted to
{150, 220, 350}; unsupported volumes rejected with `InvalidKatoriVolume`. Proven
by dedicated boundary tests.

### 14. Phone-number rule
`[IMPLEMENTED]` — `PhoneNumber` normalizes per E.164-ish digits (7–15), rejects
empty/non-numeric/too-short/too-long with `InvalidPhoneNumber`, and exposes a
**masked** representation safe for logs/rows (never the full number).

### 15. Config validation & secret-free rules
`[IMPLEMENTED]` — `config/settings.py` (pydantic-settings) validates nested
`app|database|redis|storage|identity|whatsapp|ai|observability|security` groups
under `THALI_` env prefix with `__` separators. Defaults contain **empty strings /
None for all secret-shaped keys** — no secrets, no real credentials. Verified by
`test_settings.py` (defaults, env override, section existence).

### 16. Domain event contract
`[IMPLEMENTED]` — `DomainEvent` base: `event_id`, `occurred_at`, `patient_id`,
`correlation_id`, non-empty `event_type` enforced (`DomainValidationError`). 8
concrete clinical events. Distinct from telemetry/audit (no `raw_payload`,
no `level`). Proven by `test_domain_event.py`.

### 17. Repository & port contracts
`[IMPLEMENTED]` — `Repository(Protocol, Generic[T])` contract typed with
`EntityId`-keyed methods, stdlib only, no persistence backend imported. Ports are
contracts; adapters remain `[NOT IMPLEMENTED — DEFERRED]`.

### 18. Application placeholder alignment
`[IMPLEMENTED]` — Five application command/query placeholders updated to the real
domain vocabulary (`GlucoseValue`, `patient_id`) so the pure layer is the source
of truth for names.

### 19. Entity identity & separation (patient vs confirmation)
`[IMPLEMENTED]` — `Patient` aggregate identity separated from
`PatientConfirmationState`; `GlucoseObservation`/`MealObservation` carry their own
confirmation authority; `AIReviewArtifact` carries clinician review. No single
mutable blob; each record keeps its own state machine.

### 20. NOT-IMPLEMENTED — explicit exclusions
`[NOT IMPLEMENTED — EXPLICITLY DEFERRED/EXCLUDED BY GATE SCOPE]`

| Excluded item | Status |
| :--- | :--- |
| PostgreSQL / SQLAlchemy persistence | Not implemented — 0 migrations |
| Alembic baseline migrations | Not implemented |
| Redis cache boundary code | Not implemented (package exists, empty) |
| S3 / object storage adapters | Not implemented |
| Keycloak / real identity provider | Not implemented |
| Meta/Facebook WhatsApp cloud API integration | Not implemented |
| OpenAI / generative-AI services | Not implemented (ReviewAuthority modeled only) |
| FastAPI v2 HTTP endpoints | Not implemented — `backend/interfaces/http/v2` empty |
| Mobile app | Not implemented (`apps/mobile` README boundary only) |
| Admin Web | Not implemented |
| Secrets / real credentials | Not shipped — config defaults empty |
| Compatibility adapters **activated** | Not activated (`LegacyStoreAdapter` names only) |
| Moves of `app/static/*` | Not moved — legacy dashboard remains in place |
| Replacement of `app/config.py` | Not replaced — legacy config still live |
| Relocation of `tests/test_linking.py` / `tests/test_pipeline.py` | Not moved |
| Any edit to legacy `app/**` | Not edited |

### 21. Test evidence
`[IMPLEMENTED]` —
```
.venv/bin/pytest tests -q
105 passed, 40 warnings in 2.52s
```
57 baseline (unchanged expectations, **zero edits** to baseline tests) + **48 new
Gate 03 tests** (domain 45 + config 3). No baseline test modified.

### 22. Audit evidence (dependency + static + circular imports)
`[IMPLEMENTED]` —
- grep of `backend/domain/**` for forbidden/outer-layer imports → **0 matches**.
- All domain modules import cleanly via a single-interpreter pass → **no cycles**.

### 23. Legacy compatibility evidence
`[IMPLEMENTED]` — verified after Gate 03 work:
```
from app.core.datamodel import Store        -> OK
   tables: audit, avoid_items, caregivers, meals, outbound, patients,
           raw_inbound, readings, webhook_events, windows   (10/10 intact)
from app.config import Settings             -> OK
from app.server.main import create_app      -> returns FastAPI app
Store(path=...)                             -> constructs and opens legacy schema
```

### 24. Git evidence
`[IMPLEMENTED]` — see Git checkpoint section below (commit + annotated tag created
on `feature/gate-03-domain-models`; working tree clean after checkpoint).

### 25. Known limitations
1. Domain contracts are stdlib-only by design but **no domain persistence
   adapter** exists yet — objects are ephemeral until Gate 04 governance.
2. `config/` is the *new* boundary — runtime still reads `app/config.py`; the
   switchover is a controlled later-gate action.
3. Information-asymmetry is enforced at the model level; enforcement at HTTP/DTO
   serialization is deferred to the interfaces gate.
4. `ReviewAuthority.PATIENT_CONFIRMATION` is modeled but not yet wired to the
   confirmation flow in legacy `app`.
5. pydantic-settings is the single new production dependency (plus its transitive
   `python-dotenv`); no lockfile snapshots added.

### 26. Recommendation
`[PASS]` — GATE 03 criteria satisfied: pure domain contracts extracted, config
boundary established, baseline suite green, legacy untouched, audits clean.

---

## Git checkpoint

```
Checkpoint commit:  feat(domain): establish pure THALI-PLATE domain contracts
Tag:               gate-03-domain-extraction-complete   (annotated)
Branch:            feature/gate-03-domain-models
```

Pre-tag evidence:

```
git status --short  (before checkpoint)
 M backend/application/commands/ingest_glucose_reading.py
 M backend/application/commands/link_patient_phone.py
 M backend/application/commands/log_meal_draft.py
 M backend/application/queries/build_clinical_report_context.py
 M backend/application/queries/compute_window_metrics.py
 M backend/domain/entities/__init__.py
 D backend/domain/entities/care_plan.py
 D backend/domain/entities/care_team_membership.py
 M backend/domain/entities/caregiver_relationship.py
 D backend/domain/entities/facility.py
 M backend/domain/entities/medication_plan.py
 D backend/domain/entities/organization.py
 D backend/domain/entities/patient_profile.py
 D backend/domain/entities/user.py
 M backend/domain/events/__init__.py
 M backend/domain/events/base.py
 M backend/domain/exceptions/__init__.py
 M backend/domain/repositories/__init__.py
 M backend/domain/value_objects/__init__.py
 D backend/domain/value_objects/glucose_measurement.py
 M backend/domain/value_objects/meal_portion.py
 M backend/domain/value_objects/phone_number.py
 M backend/domain/value_objects/time_window.py
 M backend/domain/value_objects/uhid.py
 M config/README.md
?? backend/domain/entities/ai_artifact.py
?? backend/domain/entities/care_task.py
?? backend/domain/entities/care_team_member.py
?? backend/domain/entities/document_reference.py
?? backend/domain/entities/glucose_observation.py
?? backend/domain/entities/meal_observation.py
?? backend/domain/entities/patient.py
?? backend/domain/entities/projections.py
?? backend/domain/events/clinical.py
?? backend/domain/value_objects/confirmation.py
?? backend/domain/value_objects/glucose.py
?? backend/domain/value_objects/katori_volume.py
?? config/__init__.py
?? config/example.env
?? config/settings.py
?? tests/unit/config/
?? tests/unit/domain/
```

Expected: 24 created, 19 modified, 7 deleted, 1 dependency,
0 migrations, working tree clean after checkpoint.

---

## Failure-safety report

| Check | Result |
| :--- | :--- |
| Baseline tests before Gate 03 | 57 passed |
| Baseline tests after Gate 03 | 105 passed (57 unchanged + 48 new) |
| Baseline tests edited | none |
| Legacy `app/**` modified/deleted | none |
| Legacy config replaced | no — `app/config.py` untouched |
| Database modified | none |
| Dependency added | 1 (`pydantic-settings`, recorded) |
| Architecture boundary violation (domain→outer) | none (grep clean) |
| Secrets committed | none (all secret keys default empty) |
| Git checkpoint problem | none (commit + tag created cleanly) |
| Working tree | clean after checkpoint |