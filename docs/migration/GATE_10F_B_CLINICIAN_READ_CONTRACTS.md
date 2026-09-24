# Gate 10F-B: Clinician Read Contracts

Status: IMPLEMENTED
Branch: `feature/gate-10f-b-clinician-read-contracts`
Supersedes gate: 10F-A (backend-only Doctor/P.L.A.T.E. AI review + medication plan creation)

## Scope

Backend-only read contracts that unblock the approved Gate 10F mobile slice
(Doctor/P.L.A.T.E. AI review queue and medication-plan workflows). No mobile
source changes are part of this gate. Every contract below is an authenticated,
authorized, facility-scoped, read-only GET.

## Routes Added

| Method | Path | Resource audited | Notes |
|---|---|---|---|
| GET | `/api/v2/clinical/ai-artifacts` | `ai_artifact.queue` | PENDING_REVIEW artifacts only, doctor/sysop |
| GET | `/api/v2/clinical/ai-artifacts/{artifact_id}` | `ai_artifact` | facility + tenant scoped, active patient |
| GET | `/api/v2/clinical/clinical-observations` | `patient.clinical_observation_feed` | clinician feed incl. carbs/GI analytics |
| GET | `/api/v2/clinical/medication-plans` | `patient.medication_plan_list` | facility scoped, active patients |
| GET | `/api/v2/clinical/medication-plans/{plan_id}` | `patient.medication_plan` | facility + tenant scoped, active patient |
| GET | `/api/v2/patients` | `patient.cohort` | facility cohort, active patients |
| GET | `/api/v2/patients/{patient_id}` | `patient` | facility + tenant scoped, active patient |

All routes use `TIERS["read"]` rate limiting and `audit_dependency(... atomic=False)`
with `AuditAction.READ`; GETs carry no Idempotency-Key (stateless reads).

## Authorization

- Authentication via Keycloak JWT (existing auth shell), verified JWKS.
- Coarse RBAC `authorize_or_403` before facility scoping.
- `assert_clinician_facility_context(ctx, uow)` derives the authoritative
  facility from the authenticated member record:
  - missing member / inactive member / member without facility / JWT facility
    claim conflicting with the member facility each yield `403`.
- Detail routes additionally call `assert_authorized_clinician_facility(ctx, uow,
  resource.tenant_id, resource.facility_id)`:
  - cross-facility access to a resource in the same tenant -> `403`.
  - cross-tenant access -> `404` (tenant-scoped repository lookup cannot find the row).
  - deactivated patient -> `403` (explicit active check).
- Patient and caregiver tokens are denied at coarse RBAC for every one of these
  routes regardless of capabilities or identity mappings (contract-tested).

## Data Access Semantics

- Repos are tenant-scoped (RLS-equivalent `tenant_id` filtering in every query).
- AI artifact queue: `AIReviewArtifactRepository.list_by_state(ReviewState)` in
  `backend/infrastructure/persistence/repositories/ai_artifact_repo.py` returns
  only `PENDING_REVIEW` artifacts, deterministically ordered by `(created_at, id)`.
- Medication plans: `MedicationPlanRepository.list()` ordered by `(created_at, id)`;
  queue and plan handlers filter to the caller facility + active patients.
- Patient cohort: `PatientRepository.list()` filtered to facility + active.
- A client-supplied `facility_id` query param cannot widen (or narrow) scope; the
  facility is always taken from the authenticated member. Contract-tested.

## Information Asymmetry

- carbohydrates / glycemic-index analytics are exposed ONLY on the clinician
  feed (`clinical-observations`). The patient-facing feed
  (`/api/v2/clinical/observations`) is contract-tested to never include
  `carbs_grams` / `glycemic_index` item fields, even for a clinician caller.
- The AI artifact detail returns the full stored review `payload`; the queue
  returns summaries. Both carry no patient clinical values beyond identifiers.

## New Application-Layer Pieces

- Handler DTOs: `backend/application/dtos/clinician_reads.py`
  (`AIReviewArtifactRecord`, `AIReviewArtifactList`, `MedicationPlanRecord`,
  `MedicationPlanList`, `PatientRecord`, `PatientList`).
- Queries: `ListAIReviewArtifacts`, `GetAIReviewArtifact`,
  `ListMedicationPlans`, `GetMedicationPlan`, `ListPatients`, `GetPatient`.
- Handlers: `services/{list_ai_review_artifacts,get_ai_review_artifact,
  list_medication_plans,get_medication_plan,list_patients,get_patient}.py`.
- Repo contracts: `MedicationPlanRepository.list()` and
  `AIReviewArtifactRepository.list_by_state(ReviewState)` added to
  `backend/application/ports/repositories.py`. Patient list already existed.
- Strict response schemas: `AIArtifactListResponse`, `MedicationPlanListResponse`,
  `PatientSummaryResponse`, `PatientListResponse`.

## Test Coverage

- `tests/api/test_gate_10f_b_clinician_read_contracts.py` (CG10F-01..46):
  role gates (patient/caregiver denied even with self-mapping/full read caps),
  cross-facility 403, cross-tenant 404, deactivated 403, missing 404,
  queue pending-only + ordering, carbs/GI exposure only on clinician feed,
  client facility param cannot widen scope, admin/sysop deny for patient cohort.
- `tests/unit/application/test_gate_10f_b_read_handlers.py`: handler-level
  facility/active/limit/ordering/filter logic and `EntityNotFound` paths.
- `tests/api/conftest.py`: new `seed_ai_artifact(state=...)` state param and
  `seed_medication_plan` helper.
- Full suite: `./.venv/bin/pytest -q` -> `582 passed` (518 baseline + 64 new).

## Limitations / Non-Goals

- No pagination beyond server-side ordering; a page-limit param may be added at
  the consumer's request in a later gate.
- No mobile client changes in this gate.
- No AI self-approval flow and no AI-authored medication plans; those remain
  out of scope for Gate 10F.