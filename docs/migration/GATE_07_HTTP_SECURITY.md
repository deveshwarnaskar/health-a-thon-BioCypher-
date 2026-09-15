# GATE 07 — HTTP Transport, Dependency Injection & Security Boundary

**THALI × P.L.A.T.E. Production Program — Gate 07: FastAPI HTTP transport for
the verified v2 API, wiring authenticated JWT identity through
dependency-injected application handlers to the multi-tenant persistence
boundary with RLS.**

- **Status:** PASS
- **Branch:** `feature/gate-07-http-security`
- **Gate 06 (predecessor):** `c6c7614` / `gate-06-api-security-complete`
- **Gate 07 migration doc (this file):** `docs/migration/GATE_07_HTTP_SECURITY.md`

---

## 1. Gate objective

Stand up the **HTTP transport boundary** (`backend/interfaces/http/`) around
the existing Gate 04 application layer and Gate 05 persistence adapters so that:

1. every inbound request is a **deny-by-default** flow: cryptographically
   **verified JWT → `AuthenticatedContext` → coarse `AuthorizationPolicy` →
   tenant-bound `UnitOfWork` → transaction-local PostgreSQL RLS**;
2. the HTTP layer is **thin** — no ORM imports, no legacy `app`/`apps` imports,
   no SQL, no business logic — it only wires already-existing
   application/domain contracts;
3. errors are **information-safe**: internals and exception details are never
   exposed; every response carries a correlation id;
4. webhook and JSON channels both verify signatures **before** trusting any
   body content;
5. the boundary is **integration-tested over real PostgreSQL RLS** when a local
   Postgres is available, and fully covered over SQLite otherwise.

## 2. Starting checkpoint

| Item | Value |
| :-- | :-- |
| Gate 06 commit | `c6c7614` |
| Gate 06 tag | `gate-06-api-security-complete` |
| Gate 06 test baseline | 226 (all passing) |

Gate 07 starts from that checkpoint and is **additive** on the HTTP layer.
Gate 06 crypto primitives (`verify_hs256`, `verify_x_hub_signature_256`,
`challenge_response`, `role_tokens`) are **reused, not rewritten or weakened**.

## 3. Files created (Gate 07)

HTTP boundary root:

- `backend/interfaces/http/__init__.py`
- `backend/interfaces/http/app.py` — `create_app()` application factory:
  routers, CORS, security headers, correlation id, request-size protection,
  exception-registration, OpenAPI bearerAuth, production hardening.
- `backend/interfaces/http/dependencies.py` — the FastAPI dependency graph:
  config getters, `get_verified_claims`, `get_authenticated_context`,
  `get_unit_of_work` (binds `ctx.tenant_id` → `SqlAlchemyUnitOfWork`),
  `get_event_publisher`, `get_clock`, `get_id_generator`, `reset_config_cache`.
- `backend/interfaces/http/errors.py` — safe exception→HTTP mapping
  (`RequestValidationError`, `HTTPException`, domain/application exceptions,
  catch-all): stable codes, no detail echo, correlation id attached.
- `backend/interfaces/http/middleware/__init__.py` + `middleware/security.py`:
  `CorrelationIDMiddleware`, `SecurityHeadersMiddleware`.

v2 routers and schemas:

- `backend/interfaces/http/v2/router.py` — aggregates the API v2 sub-routers.
- `backend/interfaces/http/v2/schemas/__init__.py` + `models.py` — strict Pydantic
  request/response DTOs (`extra="forbid"`, strict types).
- `backend/interfaces/http/v2/auth/router.py` — `GET /api/v2/auth/verify`.
- `backend/interfaces/http/v2/clinical/router.py` — `/api/v2/clinical/…`.
- `backend/interfaces/http/v2/webhooks/router.py` — `/api/v2/webhooks/whatsapp`.
- `backend/interfaces/http/v2/health/router.py` — `/health/live`, `/health/ready`.

v2 security:

- `backend/interfaces/http/v2/security/authorization.py` — `AuthenticatedContext`,
  `Operation`, `DefaultAuthorizationPolicy` (coarse role→operation matrix).
- `backend/interfaces/http/v2/security/scoping.py` — `authorize_or_403`,
  `deny_unavailable_identity`, `assert_tenant_scoped_patient`.

Tests (Gate 07):

- `tests/api/conftest.py` — config isolation, `make_jwt`/`bearer`, SQLite app/
  UoW fixtures, seed helpers.
- `tests/api/test_auth.py` — JWT→`AuthenticatedContext` verification boundary.
- `tests/api/test_authorization.py` — deny-by-default role/operation matrix +
  facility scoping.
- `tests/api/test_tenant_http.py` — HTTP→UoW→RLS tenant isolation chain (SQLite).
- `tests/api/test_http_rls_postgres.py` — same chain over real PostgreSQL RLS
  (auto-skips when Postgres is unavailable).
- `tests/api/test_whatsapp_webhook.py` — webhook signature-first GET/POST.
- `tests/api/test_http_security.py` — headers, CORS origins, correlation id,
  request-size limits, 413/400.
- `tests/api/test_dto_asymmetry.py` — patient vs clinician DTO leakage checks.
- `tests/unit/architecture/test_http_import_boundaries.py` — AST import audit.

## 4. Files modified

- `config/settings.py` — added `app_secret` to `WhatsAppConfig` (webhook HMAC
  secret, separately configurable from the JWT secret).
- `backend/interfaces/http/middleware/__init__.py` — re-exports the new
  middleware implementation.

## 5. Request pipeline (deny by default)

```
UNTRUSTED REQUEST
  → correlation id + security headers (middleware)
  → request-size protection (Content-Length bound, 8 MiB)
  → CORS (allow-list per environment)
  → HTTPException / validation / domain-eror mapping
  → dependency graph:
      JWT Bearer
        → verify_hs256 (Gate 06 primitive)          [401 on any failure]
        → AuthenticatedContext (tenant, actor, roles)
        → DefaultAuthorizationPolicy                [403 deny-by-default]
        → UnitOfWork(tenant_id) → session RLS scope  [404/empty cross-tenant]
  → application use-case handler (Gate 04, unchanged)
  → domain → repos → Postgres (RLS enforcement)
```

Nothing is ever trusted from the request body: no `tenant_id`, no prescriber,
no reviewer. `extra="forbid"` rejects body fields that try to override the
authenticated tenant/actor.

## 6. Authentication (JWT → identity)

`dependencies.get_verified_claims` (on every protected route):

- requires `Authorization: Bearer <jwt>`;
- delegates signature verification to Gate 06 `verify_hs256` (**stdlib HS256,
  constant-time**, `alg` allow-list, never `alg=none`);
- validates subject, expiration, issuer;
- requires the `tenant_id` claim (missing/malformed ⇒ 401);
- rejects structurally-malformed tokens and malformed role claims with a
  401 (fail closed) — never a 500.

`dependencies.get_authenticated_context` builds `AuthenticatedContext`:
`actor_id`, `tenant_id`, `facility_id` (optional), `roles`. `GET
/api/v2/auth/verify` returns this verified identity (never roles-derived
clinician data).

## 7. Authorization (coarse RBAC, deny-by-default)

`DefaultAuthorizationPolicy` maps `role → permissions` using the Gate 06
`role_tokens` normalization:

| Role | Permissions |
| :-- | :-- |
| `doctor`, `nurse`, `dietitian`, `care_coordinator`, `field_health_worker` | clinical read/write operations |
| `admin` | `ADMIN` only |
| `patient`, `caregiver` | **empty** — deny everything (Gate 08) |

- unknown/absent roles ⇒ empty permission set (no silent grant);
- every guarded operation asserts the required `Operation` with
  `authorize_or_403`; missing permission ⇒ 403;
- clinician patient access additionally requires the **same facility**
  (`assert_tenant_scoped_patient`): a doctor from facility A cannot read
  facility B records even within the same tenant ⇒ 403/404;
- `caregiver`/`patient` own-record access is **explicitly not** granted
  (identity→patient bridge is a Gate 08 contract, matching Gate 06 §10-A/B).

## 8. Tenant → UoW → RLS binding (proven end-to-end)

`get_unit_of_work(ctx)` constructs `SqlAlchemyUnitOfWork(session_factory,
ctx.tenant_id)`. On PostgreSQL this UoW executes
`SELECT set_config('app.current_tenant_id', :tid, true)` for the session, so
every repository query in the request runs under that tenant context and is
enforced by the database-level **FORCE ROW LEVEL SECURITY** policies
(Gate 05 migrations):

- Tenant A reading via HTTP sees only tenant A rows.
- Tenant B reading via HTTP sees only tenant B rows.
- Cross-tenant reads/writes return 404/403 (repo scoping + RLS).
- Raw-SQL proof (non-superuser role): empty/unknown tenant context ⇒ 0 rows;
  matching context ⇒ exactly the tenant's rows.

This chain is verified on **real PostgreSQL** in
`tests/api/test_http_rls_postgres.py` (auto-skip when no local PG) and on
SQLite via repository-level tenant scoping in `tests/api/test_tenant_http.py`.

## 9. Webhook channel (signature-first)

`GET /api/v2/webhooks/whatsapp` — verify-token challenge handshake using Gate 06
`challenge_response`: echoes `hub.challenge` only when token matches and mode is
`subscribe`.

`POST /api/v2/webhooks/whatsapp` — verifies `X-Hub-Signature-256` over the
**raw body bytes** (Gate 06 `verify_x_hub_signature_256`) *before* any JSON
parse; responds `202` on a verified event; the raw body is never logged and
replay/idempotency is explicitly deferred to Gate 09.

## 10. Error boundary (information-safe)

`errors.py` maps exceptions to stable JSON `{"error": {"code", "message"}}`
with the correlation id, for every handler:

- validation → `422 VALIDATION_ERROR`;
- `HTTPException` → safe semantics by status (`401 AUTHENTICATION_REQUIRED`,
  `403 AUTHORIZATION_DENIED`, `404 RESOURCE_NOT_FOUND`, `413 PAYLOAD_TOO_LARGE`,
  …) — **exception detail is never echoed**;
- domain/application errors (`EntityNotFound`, `InvalidStateTransition`, …) →
  safe codes;
- catch-all `Exception` → `500 INTERNAL_ERROR`, details only to server logs.

No internals, stack traces, or exception text are released to the client.

## 11. Transport safety

- **Security headers**: `X-Frame-Options: DENY`, `X-Content-Type-Options:
  nosniff`, `X-XSS-Protection: 0`, `Referrer-Policy: no-referrer`,
  `X-Permitted-Cross-Domain-Policies: none`; `Strict-Transport-Security`
  enabled on non-development environments.
- **CORS**: allow-list per environment; development allows only localhost/
  127.0.0.1 origins; no wildcard.
- **Correlation id**: generated per request, attached to every response via
  `X-Correlation-Id`, threaded into error payloads.
- **Request size**: `Content-Length` bound (8 MiB) → `413`; malformed header →
  `400`. Prevents unbounded webhook/JSON body ingestion.
- **Docs/OpenAPI**: disabled outside development; enabled dev docs annotate
  the global `bearerAuth` scheme on the OpenAPI security router.

## 12. OpenAPI / version boundary

- Routers are mounted at `/api/v2/...`; health at `/health/live` and
  `/health/ready`.
- Exposed OpenAPI paths (7): auth verify, observations GET/POST,
  medication-plans POST, ai-artifact review POST, whatsapp GET/POST, plus
  versioned OpenAPI docs in dev.
- API version boundary is explicit: v2 is the only version the HTTP transport
  exposes.

## 13. Left as NOT-IMPLEMENTED (deferred, not faked, STOP-guarded)

| # | Item | Exact missing contract | Why deferred |
| :-- | :-- | :-- | :-- |
| A | Patient/caregiver `GET` feeds and own-record self-access | A verified identity↔patient bridge and a persisted + queryable caregiver relationship (Gate 08) | `DefaultAuthorizationPolicy` grants `patient`/`caregiver` **zero permissions**; the HTTP layer denies (403) rather than inventing an unsafe link. |
| B | Patient-facing medication/AI endpoints | Post-Gate-04 query use-case contracts for those resources | No query contract exists for outside clinicians; only contracts with handlers were exposed. |
| C | Webhook replay protection / idempotency / rate limiting | A dedup store and a rate-limiter at the boundary (Gate 09) | Explicitly deferred; no claim of replay-protected delivery. |
| D | Audit-log persistence of HTTP decisions | A persisted audit port (Gate 09) | Denials are correlated in logs via correlation id only. |

Gate 08/09 may only be opened when their exact contracts exist. The HTTP
boundary **denies** all not-yet-authorized paths.

## 14. Dependency / import discipline

`tests/unit/architecture/test_http_import_boundaries.py` statically (AST)
audits every file under `backend/interfaces/http/`:

- allowed top-level packages only (`backend`, `config`, fastapi/starlette,
  pydantic, stdlib);
- **forbidden**: `backend.infrastructure.persistence.models|repositories|
  mappings`, `app.`, `apps.`, `backend.legacy`;
- no circular imports; every module importable.

The HTTP layer may reuse the persistence **UoW factory** (approved Gate 05
infrastructure adapter) but never touches ORM models or mappers directly.

## 15. Test matrix (Gate 07, all green)

| Area | Tests | Coverage |
| :-- | :-- | :-- |
| Auth boundary | `tests/api/test_auth.py` | missing/malformed/tampered/expired tokens, unsupported alg, bad issuer, missing subject/tenant, malformed role claims ⇒ 401 |
| Authorization | `tests/api/test_authorization.py` | deny-by-default, doctor creates plan, patient cannot approve AI artifact, facility scoping |
| Tenant isolation (SQLite) | `tests/api/test_tenant_http.py` | own-tenant reads, cross-tenant denial, body `tenant_id` override rejected, UoW tenant binding |
| Tenant isolation (Postgres RLS) | `tests/api/test_http_rls_postgres.py` | HTTP→UoW→RLS chain + raw-SQL RLS proof (auto-skip w/o PG) |
| WhatsApp webhook | `tests/api/test_whatsapp_webhook.py` | handshake, verify-before-parse, tampered body ⇒ 401/400 |
| HTTP transport security | `tests/api/test_http_security.py` | headers, CORS, correlation id, size limits (413/400) |
| DTO asymmetry | `tests/api/test_dto_asymmetry.py` | patient DTO never leaks clinician-only fields |
| Import audit | `tests/unit/architecture/test_http_import_boundaries.py` | 3 architecture tests |

## 16. Test results (full suite)

```
Gate 06 security (tests/security):                   17 passed
Gate 07 API + architecture (tests/api + unit/arch):  94 passed
FULL SUITE:                                          321 passed, 0 failed
```

(Gate 06 crypto tests remain green — primitives reused, not rewritten.)

## 17. Exit criteria checklist

- [x] FastAPI application factory with real dependency injection
- [x] Verified-JWT authentication with `AuthenticatedContext`
- [x] Deny-by-default coarse authorization (`DefaultAuthorizationPolicy`)
- [x] Tenant → UoW → RLS binding proven over real PostgreSQL
- [x] Safe, information-minimal HTTP error mapping
- [x] Security middleware: headers, CORS allow-list, correlation id, size limits
- [x] Webhook signature-first processing (verify before parse)
- [x] OpenAPI/API version boundary; docs disabled outside dev
- [x] DTO information asymmetry (patient vs clinician)
- [x] Import/architecture audit + no circular imports
- [x] No legacy surface touched; no new dependencies
- [x] Single gate commit + annotated tag
- [x] Full suite green (321 passed, 0 failed)

## 18. Commit / tag

- **Commit:** single commit on `feature/gate-07-http-security`
- **Message:** `feat(api): establish HTTP transport and security boundary`
- **Tag (annotated):** `gate-07-http-security-complete`

## Afterword — STOP

Gate 07 is complete. The HTTP transport now enforces the full
**crypto-identity → coarse-RBAC → tenant-scoped-UoW → RLS** chain, deny by
default, on every request. Gate 08 (identity↔patient/caregiver relationship
authorization) and Gate 09 (webhook idempotency, rate limiting, audit
persistence) are **not** opened and require their exact missing contracts.