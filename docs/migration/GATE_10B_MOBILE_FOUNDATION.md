# GATE 10B — UNIVERSAL MOBILE FOUNDATION
**THALI × P.L.A.T.E. Production Program**
**Role**: Principal Frontend / Platform Architect
**Status**: IMPLEMENTATION COMPLETE — READY FOR AUDIT
**Date**: 2026-09-16

---

## 1. EXECUTIVE SUMMARY

Gate 10B establishes the universal React Native + Expo application foundation
under `apps/mobile/` — one binary covering all seven platform roles
(Patient, Caregiver, Doctor, Nurse, Care Coordinator, Dietitian, Field Health
Worker). The deliverable is a production-shaped frontend scaffold: frozen Expo
SDK 57 toolchain, design tokens, the 13 core UI primitives, the API client
with Gate 09 header contracts (correlation ID, idempotency keys), the typed
HTTP error model, client-safe environment configuration, verified-contract
Zod schemas, the auth boundary interfaces, the role/capability model with a
role-aware navigation shell, state-management partitioning, and a dual test
foundation (vitest logic + jest-expo components).

All four validation gates are green: `tsc` (no errors), `eslint` (no issues),
61 vitest tests + 3 jest-expo component tests (64 total), `expo-doctor` 21/21,
and a clean headless Metro export for Android. The backend remains untouched:
full regression **436 passed**.

## 2. SCOPE COMPLIANCE (Scope A–P)

| Area | Delivered | Notes |
| :--- | :--- | :--- |
| Scaffold | `package.json`, `app.json`, `tsconfig.json`, `metro.config.js`, `eas.json`, `index.ts`, `app/` router dir, assets | pnpm-only, SDK 57 pinned |
| tsconfig | strict + noUncheckedIndexedAccess | extends `expo/tsconfig.base` |
| Expo Router | `app/_layout.tsx`, `app/index.tsx`, `app/shell.tsx` | no fake workflows |
| Env config | `.env.example`, `src/services/api/config.ts` | EXPO_PUBLIC_* only, no secrets |
| Design tokens | `src/theming/tokens.ts` | frozen palette/spacing/type |
| UI primitives | 13 components under `src/components/primitives/` | tokens-only, a11y-first |
| API client | `src/services/api/{client,headers,errors,correlation,idempotency,config}.ts` | injectable, typed |
| Runtime DTO validation | `.strict()` Zod schemas for 5 verified contracts | `src/services/schemas/` |
| HTTP error model | 400/401/403/404/409/413/422/429/5xx mapped | safe messages, no traces |
| Role/capability model | `src/authz/{roles,capabilities,navigation}.ts` | ROLE vs CAPABILITY |
| Auth boundary | `src/auth/AuthSessionProvider.ts` + `authSignal.ts` | no fake refresh |
| Query foundation | `src/store/query.ts` + `src/store/uiStore.ts` | server vs client state split |
| Correlation ID | `src/services/api/correlation.ts` | secure UUIDv4 via expo-crypto |
| Idempotency keys | `src/services/api/idempotency.ts` | reuse-on-retry, regenerate-on-intent |
| Testing foundation | vitest (61) + jest-expo (3) | hybrid per review decision |
| App shell | `src/navigation/RoleAwareShell.tsx` + router screens | placeholder-only |
| Docs | this file + `.env.example` documentation | |

**Explicitly NOT implemented** (later gates): OIDC/Keycloak auth & secure token
storage (10C), patient/caregiver/clinician workflows (10D–10G), offline SQLite
+ SQLCipher + Drizzle sync (10H–10I), localization (post-MVP P1).

## 3. TOOLCHAIN & REPRODUCIBILITY

- Node `v24.14.1`, pnpm `11.9.0` (`.npmrc` → `node-linker=hoisted`,
  `minimum-release-age=0`; `pnpm-workspace.yaml` holds pnpm >=11 settings only,
  **no** `packages` field — self-contained app, not a monorepo workspace).
- **Expo SDK 57 (react 19.2.3 / react-native 0.86.3)** — selected as the
  latest stable SDK mutually compatible with Node 24 (RN 0.86 engines require
  `^22.13.0 || ^24.3.0`; Node 24.14.1 satisfies). Versions pinned from
  `expo`'s `bundledNativeModules.json` (SDK 57), verified by `expo-doctor`
  (21/21).
- Headless Metro export (`expo export --platform android`) produces a Hermes
  bytecode bundle → no SDK/NDK required for CI validation.
- Lockfile `pnpm-lock.yaml` committed; only Expo-pinned ranges use `~`/exact;
  pure-JS deps (zustand, @tanstack/react-query, react-hook-form, zod) use
  caret ranges.

## 4. ARCHITECTURE NOTES

### 4.1 Design tokens
`src/theming/tokens.ts` is the single source of truth. Palette, 4px-baseline
spacing steps, system-font scale, radii, and `touchTarget.min = 48` (WCAG 2.5.5
/ Gate 10A §16.1). Components never hard-code colors or measures; a tokens
availability test guards the frozen values.

### 4.2 API client & Gate 09 contract fidelity
Every request carries `X-Correlation-ID` (secure UUIDv4) and `Accept`;
mutations add `Idempotency-Key` + `Content-Type`. Idempotency key semantics
match the backend (`INSERT ... ON CONFLICT DO NOTHING` + RETURNING): **same
logical mutation key reused verbatim on retry; new logical mutation → new
key**. `Idempotency-Key` is generated via `src/services/api/idempotency.ts`
with an in-memory store (durable outbox persistence lands in 10H). A 401 is
collapsed into the single `auth-expired` signal consumed by
`AuthSessionProvider` (10C wires real OIDC; nothing is faked). 409s surface
`CONCURRENT_REQUEST_IN_PROGRESS` / `IDEMPOTENCY_KEY_MISMATCH` typed subtypes;
429s parse `Retry-After` (integer seconds or RFC-1123 HTTP-date). Messages are
sanitized — no stack traces, no internal error text (Gate 10A §17).
`ApiClient` rejects requests before they fire if no base URL is configured
(no hard-coded URLs).

### 4.3 Verified contracts only
`src/services/schemas/` mirrors `backend/interfaces/http/v2/schemas/models.py`
as strict Zod schemas for the five audited contracts: `AuthVerifyResponse`,
`PatientObservationFeedResponse`, `IngestGlucoseRequest/Response`,
`CreateMedicationPlanRequest/Response`, `ReviewAIArtifactRequest/Response`.
The patient-facing feed schema rejects `carbs_grams`/`glycemic_index`
(information-asymmetry invariant, tested). The clinician-only meal schema
exists as documentation only — no verified endpoint exposes it. Contracts are
registered in `contract-status.ts` so future gates can query verified/pending.

### 4.4 Auth & identity boundary
`AuthSessionProvider` (getAccessToken / refreshSession / clearSession /
getAuthenticatedContext + `onAuthExpired`/`signalAuthExpired`) defines the
contract; the `NotConfiguredAuthSessionProvider` fails loud on
`refreshSession` (`AuthNotConfiguredError`) rather than minting demo tokens.

### 4.5 ROLE vs CAPABILITY
`src/authz/roles.ts` maps backend authoritative role tokens (`doctor`,
`care_coordinator`, `field_health_worker`, …) to platform roles (unknown
tokens never map). `src/authz/capabilities.ts` records the Gate 10A §8
capability matrix per role; UI composition only — the backend policy remains
the request-time authority. `navigation.ts` freezes the placeholder
destination sets per role; `RoleAwareShell` renders the skeleton.

### 4.6 State partitioning
Zustand (`useUiStore`) holds client/UI state only (active role mode, modal
key). TanStack Query (`src/store/query.ts`) owns server state with central
error handling (QueryCache routes 401 → auth-expired signal). No JWTs, no
server entities, no form values in Zustand.

## 5. TESTING EVIDENCE

- **vitest** (11 files / 61 tests, Node env, `expo-crypto` mocked to
  `node:crypto.randomUUID`):
  token availability, API URL config + fail-loud, header assembly (bearer,
  correlation, content-type rules), correlation UUIDv4 shape/uniqueness,
  idempotency lifecycle (new key, **same-key-on-retry**, distinct mutation,
  regeneration), HTTP error mapping for 400/401/403(+reason)/404/409(+both
  subtypes)/413/422/429/500/502/503/504/network, 401 → auth-expired signal,
  403 boundaries, 429 Retry-After (integer + HTTP-date + malformed), network
  normalization, verified contract schema parsing incl. information-asymmetry
  rejection, AI-review decision enum, contract-status verified/pending, role
  mapping + no privilege fabrication, ROLE-vs-CAPABILITY separation, a11y
  props contract + 48dp target.
- **jest-expo** (1 file / 3 tests): renders the real `Button` and asserts
  `accessibilityRole="button"`, accessible name, hint, disabled state, and
  48dp minimum height (Gate 10A §16 component-level a11y).
- Full command set: `pnpm typecheck` ✓, `pnpm lint` ✓, `pnpm test` ✓ (61),
  `pnpm test:component` ✓ (3), `pnpm dlx expo-doctor@latest` ✓ (21/21),
  `pnpm export` ✓ (Android Hermes bundle emitted to `dist/`).

## 6. BACKEND ISOLATION & REGRESSION

No backend file was modified: no changes under `backend/`, `app/`,
`config/settings.py`, or DB migrations; backend tests untouched. Full
regression `.venv/bin/python -m pytest tests -q` → **436 passed**. The
untracked analysis/verification docs (GATE_05/06/09/10A/SEQ) remain uncommitted
per repo convention; this Gate 10B record itself is likewise created as an
audit artifact but left untracked, matching the GATE_09 precedent.

## 7. DEFINITION OF DONE

- [x] apps/mobile Expo monorepo scaffold, pnpm-only, SDK 57 pinned
- [x] Design tokens frozen (palette, spacing, type, radii, touch target)
- [x] 13 core primitives built on tokens, a11y-complete
- [x] API client with correlation ID, idempotency keys, auth header, error model
- [x] Verified-contract Zod schemas + contract-status registry
- [x] AuthSessionProvider boundary (no fake refresh)
- [x] Role/capability model + role-aware shell (placeholders only)
- [x] Zustand UI-only + TanStack Query foundation
- [x] Test foundation: 64 tests green across vitest + jest-expo
- [x] Validation: typecheck, lint, tests, expo-doctor 21/21, Metro export
- [x] Backend regression green (436 passed)
- [x] Gate 10B documentation created (left untracked, matching GATE_09 precedent)
- [x] Commit `feat(mobile): establish universal expo foundation` — no tag

## 8. NEXT GATES

Gate 10C (OIDC auth shell + secure token storage) then 10D Patient glucose
vertical slice, per Gate 10A §21 sequence. Frontend now has the contract
interfaces (AuthSessionProvider, ApiClient, schemas, tokens, primitives) these
slices consume.