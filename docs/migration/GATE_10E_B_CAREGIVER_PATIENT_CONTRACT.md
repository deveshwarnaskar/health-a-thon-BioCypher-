# GATE 10E-B — CAREGIVER PATIENT DISCOVERY (BACKEND CONTRACT)

## Status

Implemented, tested, and regression-clean. Backend-only contract — no mobile/frontend
code in this gate. Deployed on branch `feature/gate-10e-b-caregiver-patient-contract`.

- Parent / Gate 10D sealed commit: `b0fff318d3a36fee66c243e55d4a7c4324f80e5e`
  (seal tag `gate-10d-patient-glucose-sealed` = `dbd4a4e0bd4e2b679ce5a13656a070cc13a39afa`)
- Implementing commit: see "Commit" section below.

## 1. Endpoint

| | |
|---|---|
| Method | `GET` |
| Path | `/api/v2/caregivers/me/patients` |
| Auth | Required bearer JWT (verified RS256, Gate 10C-R). Identity and tenant are derived **exclusively** from the verified token claims → `AuthenticatedContext` (`actor_id` = `sub`, `tenant_id`). |
| Client-supplied identity | `caregiver_user_id` / `tenant_id` are NEVER accepted from query/body. The route accepts no body and ignores any unknown/extra fields (`extra="forbid"` request schema). |
| Idempotency | None (safe `GET`, non-mutating). |
| Audit | `AuditAction.READ`, resource type `caregiver.patient_list`, no resource-id extraction, non-atomic (Gate 09 audit dependency). Minimal PHI; only the relationship id is logged, never clinical data. |
| Rate limit | Gate 09 `read` tier (`120/min` burst `30`, degrade). |

## 2. Response DTO (safe, minimal)

Response model `CaregiverPatientListResponse` (strict schema, `extra="forbid"`):

```json
{
  "patient_count": 1,
  "items": [
    {
      "relationship_id": "…uuid…",
      "patient_id": "…uuid…",
      "relationship_label": "test-caregiver",
      "status": "verified",
      "capabilities": ["read_glucose", "read_meal"],
      "expires_at": null,
      "name": "…display name…"
    }
  ]
}
```

- `status` is a `Literal["verified"]` — only verified relationships are ever returned.
- `capabilities` returns the relationship's **actual** capability tokens verbatim
  (`read_glucose`, `create_glucose`, `read_meal`, `create_meal`,
  `read_medication_events`, `create_medication_events`, `read_care_tasks`,
  `complete_care_tasks`). No capabilities are invented, converted, or expanded.
- Explicitly NOT exposed (by design / asymmetry with Gate 08 domain objects):
  glucose values, glycemic index, TIR/TAR/TBR/GMI, CV, risk scores, treatment or
  medication-plan content, recommendations/AI-review artifacts, audit internals,
  relationship idempotency/version/update metadata, secrets.

## 3. Authorization chain (deny-by-default)

```
JWT (verified, Keycloak RS256) ──▶ AuthenticatedContext (actor_id, tenant_id, roles)
   └─▶ authorize_or_403(ctx, RelationshipAuthorizationPolicy, Operation.LIST_CAREGIVER_PATIENTS)
            └─ roles: "caregiver" REQUIRED (patient/nurse/doctor/admin/unknown → 403; no admin bypass)
   └─▶ Query: ListCaregiverPatients(caregiver_user_id=ctx.actor_id)
   └─▶ ListCaregiverPatientsHandler(uow, clock)
            └─ relationship repo is tenant-scoped (tenant_id bound from Context → UoW)
            └─ patient resolution per relationship (EntityNotFound → skipped)
```

Gate 08 observation paths are unchanged: caregiver read still requires
`read_glucose` + `read_meal`, write requires `create_glucose`; patient/nurse/doctor
semantics are preserved.

## 4. Relationship filtering (exact matrix)

A relationship is returned if and only if **all** hold:

```
tenant_id        == ctx.tenant_id            (repository-level tenant binding)
caregiver_user_id == ctx.actor_id            (from verified token sub)
status           == "verified"
revoked_at       IS NULL
expires_at       IS NULL  OR  now < expires_at
patient exists   (EntityNotFound → skip, do not leak)
patient.active   == true                     (deactivated-patient invariant)
```

`ListCaregiverPatientsHandler.handle` applies this matrix; results are grouped into
`CaregiverAuthorizedPatient` value objects and exposed as `CaregiverPatientList`.

## 5. Deactivated-patient invariant (authorization boundary)

`patient.active == true` is enforced **at the authorization boundary**, consistently
for both caregiver discovery and caregiver patient-specific (observation) access:

1. `RelationshipAuthorizationPolicy`: proxy/caregiver relationship checks resolve the
   patient and require `active == true`; any resolution failure fails closed (`False`).
2. `ListCaregiverPatientsHandler`: the discovery filter also requires `active == true`.

Self-access and clinician semantics are preserved (Gate 08 unchanged). Sibling
patient-specific caregiver operations continue to route through
`authorize_patient_operation` → `_is_relationship_allowed`, so the invariant holds
there without naively duplicating endpoint logic.

## 6. Tenant security / RLS

- Identity/tenant originate only from the verified JWT → `AuthenticatedContext` →
  UnitOfWork tenant → tenant-scoped repositories → `WHERE tenant_id = …` in every
  query. No tenant value is ever supplied by the client.
- Gate 08 migration `0002` enables `ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`
  on `caregiver_relationships` (and `identity_patient_mappings`) with policy
  `tenant_isolation_<table>` keyed on `app.current_tenant_id`. PostgreSQL therefore
  fails closed at the engine even if an application layer is bypassed.
- Cross-tenant patients are never returned: verified both at the API level
  (CG10B-10/11) and at the live PostgreSQL engine level (RLS integration tests).

## 7. Live PostgreSQL + RLS verification

A local PostgreSQL server is available in the dev environment. New integration tests
in `tests/integration/test_gate_10e_b_caregiver_discovery_rls.py` run alembic `head`
migrations including the Gate 08 RLS policies, exercise the discovery query against a
real engine, and then assert RLS directly via a non-superuser role
(`thali_app_test_role`, `NOBYPASSRLS`):

- no tenant context → `0` rows from `caregiver_relationships` (fail closed)
- tenant A context → only tenant A rows; tenant B context → only tenant B rows
- deactivated patient's row remains visible under RLS to its own tenant, proving the
  `active == true` exclusion is enforced at the authorization boundary (not faked by
  RLS); the discovery query returns `patient_count == 0` after deactivation.

## 8. Security tests — CG10B-01..18

`tests/api/test_gate_10e_b_caregiver_discovery.py` (28 tests: CG10B-01..18 + extras):

| ID | Assertion |
|---|---|
| CG10B-01 | Verified caregiver with read caps discovers its patient, correct safe DTO |
| CG10B-02 | Non-caregiver roles denied (403), no bypass |
| CG10B-03 | No verified relationships → `patient_count == 0` (no leak) |
| CG10B-04 | Pending relationship not returned (status filter) |
| CG10B-05 | Expired relationship excluded (expires_at in past) |
| CG10B-06 | Deactivated patient excluded (active-patient invariant) |
| CG10B-07 | Unknown patient id on relationship → skipped, not 500 |
| CG10B-08 | `expires_at` null → still returned |
| CG10B-09 | Revoked relationship excluded |
| CG10B-10 | Cross-tenant patient never returned (same caregiver id, other tenant) |
| CG10B-11 | Patient/nurse/doctor denied; caregiver with no rows still authorized |
| CG10B-12 | Capabilities returned verbatim (read-only set) |
| CG10B-13 | DTO strict, minimal, safe; `extra="forbid"` response validation |
| CG10B-14 | Caregiver read of observations still gated by read_capability pair |
| CG10B-15 | Caregiver write of observations still gated by create_capability |
| CG10B-16 | Capability variants (read+write; write-only read denied) |
| CG10B-17 | Deactivated patient denies caregiver observation access (authz boundary) |
| CG10B-18 | Revoked/pending relationship denies caregiver observation read |

## 9. Regression

Full backend suite on branch:

```
518 passed, 251 warnings    (SQLite app/API unit suite + live PostgreSQL integration)
```

Breakdown vs Gate 10D baseline (488 passed): + 28 CG10B API/unit tests + 2 live-PG
RLS integration tests = 518. Gate 08/09/10C-R/10D suites are included in the 518 with
no regressions. No backend linter is configured in the repository (checked).

## 10. Exclusions / scope audit

- `GET`/`POST /api/v2/clinical/observations` were **not modified**; caregiver
  observation auth remains through `authorize_patient_operation`; Gate 10D patient
  glucose behavior is unchanged.
- No migration created — Gate 08 schema already provides
  `caregiver_relationships.status / capabilities / revoked_at / expires_at / tenant_id /
  caregiver_user_id` and `patients.active`.
- No idempotency (GET), no grant/mutate/verify/revoke endpoints for caregivers,
  no self-verification, no admin bypass.
- No mobile/frontend code; no RN imports; no duplicated frontend DTOs.
- No new auth providers; JWT verification unchanged (Gate 10C-R).

## 11. Files

- `backend/application/queries/list_caregiver_patients.py` (new)
- `backend/application/services/list_caregiver_patients.py` (new)
- `backend/application/dtos/caregiver.py` (new)
- `backend/application/{queries,services,dtos}/__init__.py` (exports)
- `backend/interfaces/http/v2/schemas/models.py` + `schemas/__init__.py`
  (`CaregiverPatientListItemResponse`, `CaregiverPatientListResponse`)
- `backend/interfaces/http/v2/caregivers/{__init__,router}.py` (new)
- `backend/interfaces/http/v2/router.py` (wires `/caregivers` prefix)
- `backend/interfaces/http/v2/security/authorization.py`
  (new operation + caregiver discovery authorization + deactivated-patient invariant)
- `tests/api/test_gate_10e_b_caregiver_discovery.py` (new)
- `tests/api/conftest.py` (`seed_patient(active=…)`)
- `tests/integration/test_gate_10e_b_caregiver_discovery_rls.py` (new, live PostgreSQL)

## Commit

- `30f87ee04bf28b3f63a577b37bf06778d9c59ef5` — `feat(authz): add caregiver patient
  discovery contract` (branch `feature/gate-10e-b-caregiver-patient-contract`,
  parent `b0fff318d3a36fee66c243e55d4a7c4324f80e5e` = Gate 10D seal). No seal tag
  for this gate.