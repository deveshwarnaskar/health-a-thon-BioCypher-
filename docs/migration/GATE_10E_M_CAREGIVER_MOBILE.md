# GATE 10E-M — CAREGIVER MOBILE VERTICAL SLICE
**THALI × P.L.A.T.E. Production Program**
**Role**: Implementation Engineer / Mobile Platform Architect
**Status**: IMPLEMENTATION COMPLETE — GATE 10E-M READY FOR AUDIT
**Date**: 2026-09-17

---

## 1. EXECUTIVE SUMMARY

Gate 10E-M implements the **Caregiver Mobile Vertical Slice** (online-only): caregiver
patient discovery plus the patient glucose view/record workflow, wired directly to the
frozen Gate 10E-B backend contract (`GET /api/v2/caregivers/me/patients`) and the
existing Gate 10D clinical observation API (`/api/v2/clinical/observations`).

Design constraints honored:

1. **Backend frozen** — Gate 10E-B sealed at `30f87ee`; NOT ONE backend file is touched.
   The caregiver feature is 100 % mobile (`apps/mobile/`). Full backend regression stays
   at **518 passed**.
2. **Discovery, never search** — The caregiver sees exactly the verified, active patients
   the backend authorizes (Gate 10E-B §2/§3/§5). No tenant roster, no search UI, no
   patient picker beyond the returned DTO.
3. **Capability gating from the relationship** — UI composition derives from the
   relationship `capabilities` array returned verbatim by the backend (lowercase tokens
   such as `read_glucose`). Gate 08 completeness semantics are preserved: glucose read
   requires the `read_glucose` + `read_meal` pair; glucose write requires `create_glucose`.
4. **403 is NOT a logout** — A per-patient 403 (revoked/expired relationship, deactivated
   patient) invalidates the caregiver patient list and returns to patient selection. Only
   a 401 (auth-expired) routes to the global session signal. (401 semantics unchanged,
   Gate 10C.)
5. **Idempotency & byte-identical retries** — Glucose ingestion reuses the existing Gate 10D
   capture session (`useIngestGlucose`): the `taken_at` and UUIDv4 `Idempotency-Key` are
   locked per logical submission, preserved across 401 refresh and network retry, and
   released only on confirmed persistence (Gate 09).
6. **No offline persistence / no sync engines** — No SQLite, SQLCipher, Drizzle, AsyncStorage,
   or offline write queues. TanStack Query provides in-memory caching only. The selected
   patient is **ephemeral UI state** (`useState` in `CaregiverWorkflow`) — never persisted,
   never written to any store, never stored on disk.
7. **Clinical information asymmetry preserved** — The caregiver DTO and observation feed stay
   strictly `.strict()`; clinician-only analytics (`carbs_grams`, `glycemic_index`) can never
   reach a screen (schema boundary + `assertPatientSafeFeed` defense-in-depth, Gate 10A §13).

---

## 2. SCOPE COMPLIANCE & DELIVERABLES

| Component / File | Responsibility / Delivered Behavior |
| :--- | :--- |
| `src/services/schemas/caregiver.ts` | Strict (`extra="forbid"`) Zod DTOs mirroring the Gate 10E-B response model: `caregiverPatientListSchema`, `caregiverPatientListItemSchema`, verbatim `CAREGIVER_CAPABILITIES` enum, and UI gate helpers `canReadCaregiverGlucose` (pair) / `canRecordCaregiverGlucose` (`create_glucose`). |
| `src/services/schemas/index.ts` | Barrel export of the caregiver schemas. |
| `src/services/api/endpoints/caregiver.ts` | `caregiverEndpoints.patients` — `GET /api/v2/caregivers/me/patients`, `requiresIdempotencyKey: false` (non-mutating), response-schema validated. |
| `src/services/api/endpoints/index.ts` | Barrel export of the caregiver endpoint. |
| `src/features/caregiver/api.ts` | `fetchCaregiverPatients` typed client (safe GET, no body, no idempotency key). |
| `src/features/caregiver/useCaregiverPatients.ts` | TanStack Query hook, query key `["caregivers","me","patients"]`, 30s stale, retry 1; returns `patients`, `patientCount`, loading/error/refetch. Never persisted. |
| `src/features/caregiver/CaregiverPatientCard.tsx` | Accessible AppCard rendering only relationship-selection facts (name, relationship label, capability badges). No clinical data. |
| `src/features/caregiver/CaregiverPatientsScreen.tsx` | Discovery screen: `Caregiver` role guard, loading / empty / error / list states, selecting a card returns the full DTO. |
| `src/features/caregiver/CaregiverPatientGlucoseScreen.tsx` | Patient glucose view/record screen gated on relationship capabilities; reuses Gate 10D form/timeline/hooks; 403 ⇒ revoked-access state (not logout); view-only state when `create_glucose` absent; submit scoped to `patient.patient_id`. |
| `src/features/caregiver/CaregiverWorkflow.tsx` | Ephemeral state machine: `useState<CaregiverPatientListItem | null>` selection; patient list ⇄ selected patient glucose. Nothing persisted. |
| `src/features/caregiver/index.ts` | Clean barrel export. |
| `app/(app)/caregiver.tsx` | Dedicated Expo Router stack route mounting `CaregiverWorkflow` (gate 10D `glucose.tsx` precedent). |
| `app/(app)/shell.tsx` | Integrates `CaregiverWorkflow` when `role === 'Caregiver'` and destination `patients` selected. |
| `test/unit/caregiver-schemas.test.ts` | 10 Vitest unit tests (CG10M-01..10). |
| `test/unit/caregiver-api.test.ts` | 8 Vitest unit tests (CG10M-11..17 + Retry-After parity). |
| `test/components/CaregiverPatientsScreen.test.tsx` | 6 Jest component tests (folded into CG10M-18..22). |
| `test/components/CaregiverPatientGlucoseScreen.test.tsx` | 9 Jest component tests (folded into CG10M-23..25). |

---

## 3. SECURITY & ARCHITECTURAL INVARIANTS VERIFIED

1. **Role & relationship scoping**:
   - Only `Caregiver` actors can open the discovery screen; any other role renders an
     `Access Restricted` state at both screens.
   - Patient selection comes **only** from `GET /api/v2/caregivers/me/patients`. The list is
     enforcement-free UI — the backend remains authoritative at every request (Gate 10E-B §3).
2. **Capability gating (relationship tokens, verbatim)**:
   - Timeline visible only when the relationship carries the `read_glucose` + `read_meal` pair.
   - Entry form visible only when the relationship carries `create_glucose`; otherwise a
     `View-only access` banner is rendered.
   - No glucose capabilities ⇒ no clinical surface is rendered at all.
3. **403 ≠ logout (per-patient revocation)**:
   - A 403 on the observation feed renders `Access Revoked` and a `Back to Patient List`
     action that invalidates `["caregivers","me","patients"]` and returns to selection.
   - A 403 on ingestion has the same effect. 401s continue to flow through the shared
     query-cache auth-expired signal → session manager (Gate 10C) — never a silent loop.
4. **Idempotency lifecycle reuse (Gate 09)**:
   - `useIngestGlucose` capture session is reused unchanged: fixed `taken_at` + stable
     UUIDv4 `Idempotency-Key` across 401 refresh/network retry; byte-identical body so
     the backend HMAC fingerprint never sees `IDEMPOTENCY_KEY_MISMATCH`.
5. **Ephemeral selection state**:
   - `CaregiverWorkflow` holds the selected patient in `useState` only. It is not written to
     Zustand, disk, or AsyncStorage; each entry resolves selection from the query.
6. **Clinical asymmetry (unchanged)**:
   - `caregiverPatientListItemSchema` and the observation feed are `.strict()`; contaminated
     responses are refused at the schema boundary (`CLIENT_CONTRACT_MISMATCH`) plus
     `assertPatientSafeFeed` defense-in-depth.
7. **Backend frozen**:
   - Zero changes outside `apps/mobile/` (plus this doc). Backend suite unchanged at 518.

---

## 4. VERIFICATION EVIDENCE

### 4.1 TypeScript Compiler (`tsc --noEmit`)
```
$ tsc --noEmit
Exit code: 0 (0 errors)
```

### 4.2 ESLint (`eslint .`)
```
$ eslint .
Exit code: 0 (0 errors, 0 warnings)
```

### 4.3 Vitest Unit Tests (`vitest run`)
```
Test Files  24 passed (24)   ← 22 baseline + 2 new
Tests       160 passed (160) ← 142 baseline + 18 new
Duration    0.99s
Exit code: 0
```

### 4.4 Jest Component Tests (`jest`)
```
Test Suites: 9 passed, 9 total   ← 7 baseline + 2 new
Tests:       57 passed, 57 total ← 42 baseline + 15 new
Exit code: 0
```

### 4.5 Expo Production Export (`expo export --platform android`)
```
› android bundles (1):
_expo/static/js/android/index-….hbc (3.2MB)   ← includes caregiver route
Exported: dist
Exit code: 0
```
Note: `expo-doctor` is not installed in this environment (its binary is absent from
`node_modules`, pre-existing — the script predates this gate and the package is not in
`package.json`). The production export above performs the equivalent bundle/route integrity
check for the new route.

### 4.6 Backend Regression Suite (`.venv/bin/pytest -q`)
```
518 passed, 251 warnings in 14.87s
Exit code: 0 (backend untouched — frozen at Gate 10E-B 30f87ee)
```

---

## 5. TEST MATRIX (CG10M-01..25)

| ID | Gate / Layer | Assertion |
|---|---|---|
| CG10M-01 | schemas | Fully valid `verified` relationship item parses; capabilities verbatim |
| CG10M-02 | schemas | Non-`verified` status (e.g. `pending`) rejected |
| CG10M-03 | schemas | Strict DTO refuses unknown keys (clinician analytics included) |
| CG10M-04 | schemas | Unknown/invented capability token rejected |
| CG10M-05 | schemas | `patient_count` must be an integer |
| CG10M-06 | schemas | `expires_at` timestamp-string or `null` both accepted |
| CG10M-07 | schemas | Full list envelope parses with count + items |
| CG10M-08 | schemas | Glucose **read** gate requires the exact `read_glucose`+`read_meal` pair |
| CG10M-09 | schemas | Glucose **write** gate requires `create_glucose` only |
| CG10M-10 | schemas | Query keys deterministic and caregiver-scoped (`["caregivers","me","patients"]`) |
| CG10M-11 | api | GET `/api/v2/caregivers/me/patients` with bearer + `X-Correlation-ID` |
| CG10M-12 | api | GET sends no body and no `Idempotency-Key` (idempotency-free GET) |
| CG10M-13 | api | Endpoint definition flags `requiresIdempotencyKey: false` |
| CG10M-14 | api | Contaminated DTO (analytics fields) refused as `CLIENT_CONTRACT_MISMATCH` |
| CG10M-15 | api | `capabilities: null` refused by schema |
| CG10M-16 | api | 403 mapped to structured `FORBIDDEN` (deny-by-default, no bypass) |
| CG10M-17 | api | 401 preserved as the single auth-expired `UNAUTHORIZED` signal (not a retry loop) |
| CG10M-18 | screens | Discovered patients render with name, relationship label, capability badges |
| CG10M-19 | screens | Loading and empty states render correctly (0 authorized patients) |
| CG10M-20 | screens | Error state renders and retry refetches the list |
| CG10M-21 | screens | Selecting a patient card returns the full caregiver DTO |
| CG10M-22 | screens | Non-Caregiver roles blocked with `Access Restricted` at both screens |
| CG10M-23 | screens | Capability composition: read-only hides entry form; write-only shows form without feed; no glucose caps ⇒ no clinical surface |
| CG10M-24 | screens | Feed 403 ⇒ `Access Revoked` state + return to patient list (**not** a logout); transient failures stay retryable |
| CG10M-25 | screens | Valid submission forwarded without client `taken_at` (capture session owns it); success banner on persisted response |

---

## 6. GATE CONCLUSION

Gate 10E-M (Caregiver Mobile Vertical Slice) is complete: mobile-only, backend frozen,
idempotency and clinical-asymmetry invariants preserved, capability gating derived from
verbatim relationship tokens, 401/403 semantics correct, all validation green (typecheck,
lint, 160 unit + 57 component tests, expo export), and the backend regression suite remains
at 518 passed. Ready for independent audit. **No seal tag created** for this gate.

## Commit

- Branch `feature/gate-10e-m-caregiver-mobile` (parent `53da072` / Gate 10E-B, which chains to
  Gate 10D seal `b0fff318`).
- Message: `feat(mobile): implement caregiver patient discovery and glucose vertical slice`.