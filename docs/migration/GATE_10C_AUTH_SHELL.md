# GATE 10C — OIDC AUTHENTICATION + SECURE SESSION + ROLE-AWARE SHELL
**THALI × P.L.A.T.E. Production Program**
**Role**: Principal Frontend / Platform Architect
**Status**: IMPLEMENTATION COMPLETE — GATE 10C READY FOR AUDIT
**Date**: 2026-09-16

---

## 1. EXECUTIVE SUMMARY

Gate 10C wires real end-to-end authentication into the mobile foundation built
in Gate 10B: recommended **OIDC Authorization Code + PKCE** against
Keycloak via `expo-auth-session`/`expo-web-browser`, secure token storage via
`expo-secure-store`, a strict auth **state machine**, exactly-once
challenge-refresh-retry on 401 in the API client, and the role-aware shell with
safer denial states. Auth is built into the routers: a root flow switcher, a
protected `(app)` group, a `(auth)` group with login and not-configured screens,
and an access-denied screen. When authentication is not configured
(`EXPO_PUBLIC_AUTH_ENABLED=false`), the app fails loudly with explanatory
guidance instead of silently bypassing security.

Design follows the review decision (authorization code + PKCE with explicit
token-endpoint exchange, public client, native browser, no fake/dev login).
Backend functionality is NOT modified. Because the live backend verifies HS256
tokens and has no Keycloak realm configured, the flow is validated by unit and
component tests plus a device-agnostic Metro export; live Keycloak timing is a
documented runtime prerequisite (Section 10).

## 2. SCOPE COMPLIANCE

| Area | Delivered | Notes |
| :--- | :--- | :--- |
| OIDC config | `src/auth/oidcConfig.ts` | issuer, realm, clientId, redirect `thali://auth/callback`, `EXPO_PUBLIC_KEYCLOAK_SCOPES` (default `openid profile email offline_access`) |
| Discovery | `src/auth/discovery.ts` | `.well-known/openid-configuration` fetch + strict validation, memoized, injectable fetch |
| PKCE (RFC 7636) | `src/auth/pkce.ts` | SDK 57 `getRandomBytesAsync` + `digestStringAsync` (S256), injectable randomness, format validation |
| Token response | `src/auth/tokenResponse.ts` | strict parsing of token endpoint response; NONE for nonce (`openid` used instead) |
| Secure storage | `src/auth/secureTokenStore.ts` + `tokenStore.ts` | expo-secure-store keys `thali.auth.*`; `InMemoryTokenStore` for tests |
| Token endpoint | `src/auth/tokenEndpoint.ts` | explicit token exchange/refresh/recovery, `AuthTransientError` classification |
| OIDC flow | `src/auth/oidcFlow.ts` | `createAuthRequest` + `AuthRequest.promptAsync(discovery.authorizationEndpoint)` + `openAuthSessionAsync` for end-session; no implicit/ROPC flow |
| Session manager | `src/auth/sessionManager.ts` | signIn / signOut / restoreSession / single-flight refresh / `verifyWithBackend` (401→SESSION_EXPIRED, 403→DEACTIVATED), end-session, signal auth-expired |
| Auth state machine | `src/auth/authStateMachine.ts` | explicit ALLOWED table + pure reducer (unknown → authenticating → authorized/exchange → … → unauthenticated / failed / authenticated / session_expired / access_denied / deactivated) |
| Auth context | `src/auth/AuthProvider.tsx` + `SessionProvider.tsx` | `useAuth` hook + `AuthController`; provider bootstraps session on mount |
| Denial messaging | `src/auth/denial.ts` | safe user-facing reasons; 403 ≠ logout |
| API client | `src/services/api/client.ts` | `setAuthProvider`; on 401 exactly one refresh + one retry, same correlation ID + same Idempotency-Key; transient mapping via `mapTransientError`; no infinite loop |
| Query wiring | `src/store/query.ts` + `src/auth/globalAuthSignal.ts` | 401-driven auth-expired signal clears query cache + resets UI store |
| Routing | `app/` restructured | root `/` switch; `(auth)/login`, `(auth)/not-configured`; `(app)/shell`, `(app)/access-denied`; protected `(app)/_layout` guard |
| Shell | `app/(app)/shell.tsx` | per-role placeholder destinations, role label, sign-out (busy state) |
| Auth-disabled path | `src/auth/notConfiguredSession.tsx` + `app/(auth)/not-configured.tsx` | fail-loud guidance (no bypass) |
| Config | `src/services/api/config.ts` | `EXPO_PUBLIC_AUTH_ENABLED` + issuer/realm/clientId validated |
| Tests | vitest + jest-expo | 125 logic + 31 component tests (incl. per-role ×7 shell) |

**Explicitly NOT implemented**: patient/caregiver/clinician workflows
(Gates 10D–10G), offline SQLite + SQLCipher + Drizzle sync (10H–10I),
Keycloak server configuration (backend — see Section 10), live-environment
device verification against a running Keycloak realm.

## 3. OIDC DESIGN

- **Flow**: Authorization Code + PKCE (S256), exchange done automatically (never
  rendered) — code never touches JS-accessible app state.
- **Client**: public client; no client secret, no device-side secrets or JWTs.
- **Browser**: `expo-web-browser`/`expo-auth-session` native browser with
  `preferEphemeralSession` propagated from config.
- **Scopes**: configurable via `EXPO_PUBLIC_KEYCLOAK_SCOPES`; default includes
  `offline_access` for refresh support and `openid profile email`.
- **Redirect URI**: `thali://auth/callback`; discovered via `Linking` at
  runtime (dev vs prod config) — no event-payload redirect validation needed on
  this layer (native handling).

## 4. BACKEND INTEGRATION REALITY & RUNTIME PREREQUISITES

Read-only audit of the backend (`backend/interfaces/http/v2/security/jwt.py`,
`backend/interfaces/http/v2/auth/router.py`) shows the current production
verification path is **HS256-only** with no JWKS and no `aud` validation;
`GET /api/v2/auth/verify` returns `{actor_id, tenant_id, roles, facility_id}`
and requires a `tenant_id` claim. The mobile boundary mirrors that contract
(`src/services/schemas/auth.ts`), so Gate 10C integrates correctly **without
any backend change**: the session manager calls `verifyWithBackend` and maps
401→`session_expired`, 403→`deactivated`.

To exercise the full flow live, a Keycloak realm must be provisioned and the
backend upgraded to RS256/JWKS (documented prerequisite, intentionally NOT
in this commit):

1. **Keycloak**: create realm with client (public, `thali://auth/callback`,
   S256 PKCE, `openid profile email offline_access`).
2. **Backend** (real environment only): point verification at Keycloak JWKS
   (RS256) and keep HS256 in tests; unblock mobile 401/403 flows.
3. **Device**: install on Android/iOS, run with `EXPO_PUBLIC_AUTH_ENABLED=true`
   and correct issuer/realm/clientId/scopes.

Until then the flow is verified by the deterministic test suite below and is
safe to land (auth-disabled mode remains the visibly explicit default).

## 5. SESSION LIFECYCLE

- `SessionProvider` fetches discovery → constructs `OidcSessionManager` →
  registers it as the client's `authProvider` → renders `AuthProvider`.
- `AuthProvider` bootstraps on mount (no stored tokens → `unauthenticated`).
- On later app launches `restoreSession` touches `/auth/verify`; success keeps
  it, 401 → `session_expired` (login screen), network/5xx → `unauthenticated`
  (login still reachable) — the app never dead-ends on a transient network
  failure, and 403 → `deactivated` (access-denied screen).
- Expiry during use: API 401 → exactly one refresh → same-request retry; if
  refresh fails, `globalAuthExpiredSignal` fires → `queryClient.clear()` +
  `uiStore.reset()` → login. Single-flight guard prevents a stampede.

## 6. AUTH STATE MACHINE

States: `unknown`, `unauthenticated`, `authenticating`, `authorized`,
`exchanging_code`, `authenticated`, `session_expired`, `failed`, `access_denied`,
`deactivated`. `AuthFlowState` includes optional `category` (network / server /
configuration) and `reason` fields; transitions outside the allowed table are
rejected (defense in depth). `AuthController.isBootstrapping` /
`isUnauthenticated` / `isAuthenticated` drive the routers.

## 7. ROUTING

- `app/index.tsx` `/`: while `unknown` → `LoadingState("Restoring
  session…")`; `unauthenticated`/`session_expired`/`failed` →
  `/(auth)/login`; `authenticated` → `/(app)/shell`; `access_denied` /
  `deactivated` → `/(app)/access-denied`. Auth-disabled → `/not-configured`.
- `(app)/_layout.tsx`: guard — redirect to login/access-denied unless
  authenticated; renders shell screens.
- `(auth)/login.tsx`: sign-in button, per-state alert banner, busy state.
- `(auth)/not-configured.tsx`: guidance to set `EXPO_PUBLIC_AUTH_ENABLED`.

## 8. SECURITY & PRIVACY

- Tokens live only in `expo-secure-store`; auth module never logs token
  material, Authorization headers, patient names, or clinical values
  (`src/auth/authLog.ts`).
- Errors are user-safe (no stack traces / PII / PHI on screen).
- No `asyncStorage` imports (token store only), no third-party logging of
  auth traffic.
- Exactly-once refresh+retry; 403 surfaces the denial screen, never a logout.

## 9. VALIDATION EVIDENCE

| Check | Result |
| :--- | :--- |
| `pnpm typecheck` (`tsc --noEmit`) | 0 errors |
| `pnpm lint` (`eslint .`) | 0 errors, 0 warnings |
| `pnpm test` (vitest) | 21 files / **125 passed** |
| `pnpm test:component` (jest-expo) | 6 suites / **31 passed** (incl. per-role ×7) |
| `expo-doctor` | 21/21 checks passed |
| `expo export --platform android` | clean Metro export |
| Backend regression (`pytest tests -q`) | **436 passed** |

## 10. GO-LIVE CHECKLIST (NEXT STEP)

1. Provision Keycloak realm/client (public, S256, redirect URIs below).
2. Backend RS256/JWKS verification (explicitly out of scope for this commit).
3. Set `EXPO_PUBLIC_AUTH_ENABLED=true` + issuer/realm/clientId/scopes.
4. Device smoke test: login → shell → refresh → logout / access-denied paths.

Redirects: dev `thali://auth/callback`, prod per app scheme.