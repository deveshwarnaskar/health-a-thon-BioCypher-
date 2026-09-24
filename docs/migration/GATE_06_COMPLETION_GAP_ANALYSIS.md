# GATE 06 — COMPLETION GAP ANALYSIS

**THALI × P.L.A.T.E. Production Program — Gate 06 API + security boundary,
exact completion-gap audit (ANALYSIS ONLY).**

- **Gate 05 (canonical):** `5503ad0` — `gate-05-infrastructure-adapters-complete`
- **Gate 06 (current):** `c6c7614` — `gate-06-api-security-complete`
- **Full suite at audit time:** `226 passed`
- **Mode:** read / analyze / document. **No source, test, domain, application,
  or infrastructure change; no commit; no tag movement; no migration.**
- **Gate 07:** LOCKED (not started).

---

## 1. Executive summary

Gate 06 has genuinely implemented **four cryptographic verifier boundaries**
(HmacJwtHS256, X-Hub-Signature-256, verify-token handshake, JWT HS256) — all
stdlib-only, constant-time, byte-exact raw-body handling, deterministically
tested.

It has **not** implemented the security *boundary* around an actual **HTTP
boundary**: those verifier primitives exist today as a `security/` + `webhooks/`
sub-boundary under `interfaces/http/v2/`, but there is **no FastAPI router, no
route→use-case wiring, no dependency-injection boundary, no middleware, no
auth/authorization dependency** — in fact there is **no route binding at all**
anywhere under `backend/interfaces/http/`.

Separately, three security sub-domains that Gate 06's original 36-item matrix
included are **blocked by missing contracts, not by missing implementation**:

- **per-patient caregiver relationship authorization** — no repository port,
  no RLS path for `CaregiverRelationship`;
- **patient self-access** — no identity→patient persona bridge, no phone claim
  contract;
- **idempotency / replay / rate-limit / audit** — no ports or stores at all.

This document classifies **every** Gate 06 requirement into exactly one of
`IMPLEMENTED / PARTIALLY IMPLEMENTED / BLOCKED BY MISSING CONTRACT /
NOT YET IMPLEMENTED` and does **not** collapse anything into "PASS".

---

## 2. Current Gate 06 status

| Item | Status |
| :-- | :-- |
| Fontanelle HS256 verifier app boundary | IMPLEMENTED |
| SSL/Test-JWT verifier boundary | IMPLEMENTED |
| WhatsApp webhook boundary | IMPLEMENTED |
| HTTP transport (router / app / routes) | NOT YET IMPLEMENTED |
| Dependency-injection boundary (HTTP) | NOT YET IMPLEMENTED |
| Auth dependency for routes | NOT YET IMPLEMENTED |
| RBAC role→permission policy (authorization) | BLOCKED BY MISSING CONTRACT |
| Relationship-aware per-patient authorization | BLOCKED BY MISSING CONTRACT |
| Patient self-access | BLOCKED BY MISSING CONTRACT |
| Tenant propagation JWT→RLS | PARTIALLY IMPLEMENTED (Gate 05 RLS exists; JWT→RLS strand missing) |
| Idempotency / replay protection | BLOCKED BY MISSING CONTRACT |
| Rate limiting | BLOCKED BY MISSING CONTRACT |
| Audit / PHI-redacted logging | PARTIALLY IMPLEMENTED (redaction primitives; no audit port) |

**Verdict:** Gate 06 is **NOT complete for API security** as originally scoped;
the verifier-boundary slice is complete and green, the HTTP/authorization
slice is not.

---

## 3. Complete requirement matrix

| # | Requirement | Status | Evidence |
| :-- | :-- | :-- | :-- |
| 1 | HS256 JWT verifier (valid accept) | IMPLEMENTED | `test_jwt_hs256_signature.py` |
| 2 | HS256 verifier (tampered body reject) | IMPLEMENTED | same file |
| 3 | HS256 verifier (wrong secret reject) | IMPLEMENTED | same file |
| 4 | HS256 verifier (unsupported `alg=none`) | IMPLEMENTED | same file |
| 5 | HS256 verifier (malformed structures) | IMPLEMENTED | same file |
| 6 | HS256 verifier (malformed base64 / empty secret) | IMPLEMENTED | same file |
| 7 | HS256 verifier (deterministic field serialization) | IMPLEMENTED | same file |
| 8 | X-Hub-Signature-256 valid | IMPLEMENTED | `test_whatsapp_webhook.py` |
| 9 | X-Hub-Signature-256 tampered body | IMPLEMENTED | same file |
| 10 | X-Hub-Signature-256 wrong secret | IMPLEMENTED | same file |
| 11 | X-Hub-Signature-256 missing header | IMPLEMENTED | same file |
| 12 | X-Hub-Signature-256 empty header | IMPLEMENTED | same file |
| 13 | X-Hub-Signature-256 wrong prefix | IMPLEMENTED | same file |
| 14 | Verify-token handshake valid | IMPLEMENTED | same file |
| 15 | Verify-token handshake mismatch reject | IMPLEMENTED | same file |
| 16 | Verify-token handshake unsupported mode | IMPLEMENTED | same file |
| 17 | Inbound envelope PHI-minimal normalization | IMPLEMENTED | same file |
| 18 | OpenAPI / request schema boundary (DTO) | NOT YET IMPLEMENTED | no DTO/route layer |
| 19 | Security error boundary (safe responses) | PARTIALLY IMPLEMENTED | verifier errors are typed; no HTTP error handlers |
| 20 | RBAC authorization policy | BLOCKED BY MISSING CONTRACT | no `can_*` policy module; role tokens only |
| 21 | Per-patient caregiver authorization | BLOCKED BY MISSING CONTRACT | `CaregiverRelationship` has no repository port / RLS |
| 22 | Tenant-id isolation via RLS | PARTIALLY IMPLEMENTED | Gate 05 RLS `set_config('app.current_tenant_id')`; JWT→RLS strand missing |
| 23 | Patient self-access (own records) | BLOCKED BY MISSING CONTRACT | no identity→patient persona bridge / phone claim contract |
| 24 | Caregiver access to unlinked patient — deny | BLOCKED BY MISSING CONTRACT | needs relationship store |
| 25 | Clinician cross-facility deny | BLOCKED BY MISSING CONTRACT | facility scoping policy not represented |
| 26 | Authorized relationship allow | BLOCKED BY MISSING CONTRACT | same |
| 27 | Webhook replay protection | BLOCKED BY MISSING CONTRACT | no replay/idempotency store/port |
| 28 | Webhook idempotency / dedup | BLOCKED BY MISSING CONTRACT | no store/port |
| 29 | Rate limiting (per tenant/user/IP) | BLOCKED BY MISSING CONTRACT | no rate-limit port/adapter |
| 30 | Audit (correlation, actor, tenant, op, target) | BLOCKED BY MISSING CONTRACT | no audit port; redaction only |
| 31 | PHI redaction in logs | IMPLEMENTED | `logging` infra redaction |
| 32 | No PHI in whatsapp envelope / DTOs | IMPLEMENTED | envelope is phone+message_id+event+timestamp |
| 33 | HTTP transport / route wiring | NOT YET IMPLEMENTED | no router/app under `http/` |
| 34 | OpenAPI exposure policy | NOT YET IMPLEMENTED | no app to host it |
| 35 | DTO/dependency boundary at HTTP | NOT YET IMPLEMENTED | no DI in `http/` |
| 36 | 500 strace suppression / constant headers | NOT YET IMPLEMENTED | no error handler/middleware |

---

## 4. Authentication analysis

The key discipline requirement of the original matrix was: **"Do not equate
`HS256 verification` with `Keycloak/OIDC authentication`."** This analysis
treats them separately.

### 4.1 JWT structure validation — IMPLEMENTED

- `verify_hs256` (? uncorrected) — the whatsapp webhook/whatsapp-adapter
  boundary splits the token, base64-decodes just enough for header presence,
  checks `alg` allow-list, verifies HMAC in constant time.
- Tests: `test_jwt_hs256_signature.py` — valid / tampered / wrong-secret /
  `alg=none` / malformed / malformed-base64-empty-secret / deterministic
  serialization. **Green.**

### 4.2 HS256 cryptographic verification — IMPLEMENTED

The `jwt` boundary computes exactly `HMAC-SHA256(secret,
b64url(header) + "." + b64url(payload))` over the **canonical signature input**
and re-verifies deterministically. This is genuine signature verification.

### 4.3 Keycloak/OIDC validation — NOT YET IMPLEMENTED (deferred to identity infra)

- The Gate 05 Keycloak adapter (`backend/infrastructure/identity/...`) provides
  `KeycloakTokenValidator` that is **claims-level only**: it decodes an
  **unverified** token and validates `exp`, `iss`, `sub`, `preferred_username`,
  `realm_access.roles`, and `tenant_id` claims. It does **not** verify the
  signature, does not fetch JWKS, does not enforce `alg`.
- **Exact distinction:** Gate 06's HS256 verifier proves the *caller* holds the
  symmetric secret (signature). Gate 05's Keycloak validator proves the *token
  contents* match a trusted issuer/tenant shape. They are two different claims
  about a token and are **not interchangeable**. Nothing conflates them today —
  good.

### 4.4 Issuer validation — PARTIALLY IMPLEMENTED

Claims-level `iss` check exists in the Keycloak adapter; cryptographic
issuer/signature binding does not.

### 4.5 Expiration validation — IMPLEMENTED (claim-level)

`exp` is enforced in the Keycloak validator; the HS256 verifier itself is
agency-agnostic and does not check `exp` (correct — signature ≠ expiry).

### 4.6 Authenticated principal — BLOCKED BY MISSING CONTRACT

There is **no `AuthenticatedContext` / principal type** anywhere in domain or
application; no definition of what "the authenticated actor" is. The whatsapp
envelope is an inbound *channel* envelope, not an authenticated actor.

---

## 5. Authorization analysis

### 5.2 Client identity / RBAC role tokens — PARTIALLY IMPLEMENTED

- `backend/interfaces/http/v2/security/roles.py` normalizes realm role strings
  into canonical `CareTeamRole` tokens (additive allow-set). This is
  **role normalization**, not authorization.
- **Missing:** the role→permission **policy** (which role may perform which
  application operation). The domain provides per-role capability flags
  (`CareTeamMember.can_author_medication` etc.) on *entities*, but there is no
  application/HTTP **policy check** (no `authorize(...)` for an operation, no
  permission catalog).

### 5.3 Relationship-aware authorization — BLOCKED BY MISSING CONTRACT

- `CaregiverRelationship` exists as a **domain entity only**; there is **no
  repository port, no RLS path, no query use-case** to answer "does this
  caregiver (user) have a verified relationship with patient X?"
- The 36-matrix items 21/24/26 (caregiver → unlinked deny, clinician → cross-
  facility deny, authorized allow) are the *authorization* core and are
  **blocked**, not implementable from current contracts. A dangerous shortcut
  (e.g. "role=doctor ⇒ any patient") is **deliberately not** implemented.

### 5.4 Tenant authorization — PARTIALLY IMPLEMENTED (Gate 05 RLS)

Same RLS story as §7; policy strand (which tenant may a JWT access) is missing.

### 5.5 Resource authorization — BLOCKED

Depends on relationship + facility contracts that don't exist.

---

## 6. Identity-to-patient analysis

Required chain:

```
authenticated identity (JWT sub / Keycloak user)
  → patient persona
  → patient_id (own-records access)
```

**BLOCKED BY MISSING CONTRACT.** Exactly what is missing:

1. **Patient persona / patient identity mapping** — there is a `Patient`
   domain entity and a `link_patient_phone` command (links a patient to a phone
   number), but **no "the authenticated user IS patient X" bridge**; no claim
   `phone` or `patient_id` on the token contract is consumed.
2. **Phone-claim contract** — no authenticated-identity → phone claim adapter
   exists. `CaregiverRelationship` cannot be joined to identity at all.
3. **Repository port** for the mapping — none.

Minimum missing contract (analysis only, not implemented): an
`IdentityPatientMappingPort`/repository that resolves `(tenant_id, identity) →
patient_id`, plus a token claim carrying `phone`/`patient_ref` under verified
signature.

---

## 7. Tenant propagation analysis — PARTIALLY IMPLEMENTED

Verified links today:

```
Keycloak adapter: tenant_id claim extracted  (claims-level)
      ↓
(sqlalchemy UoW): set_config('app.current_tenant_id', :tid)   ← Gate 05 RLS, implemented
      ↓
PostgreSQL RLS: app.current_tenant_id filter                     ← Gate 05 RLS, implemented
```

Missing link:

```
JWT (verified HS256 / Keycloak claims)
  → AuthenticatedContext {tenant_id}
      → UnitOfWork(tenant_id=...)          ← the HTTP boundary must set this
```

The **HTTP boundary does not exist**, so the JWT→UoW strand is un-wired.
Gate 05 proved transaction-local RLS works; it is **not** correct to mark
"tenant propagation = done" just because Gate 05 RLS works.

---

## 8. API analysis

| Artifact | Status |
| :-- | :-- |
| FastAPI application | NOT YET IMPLEMENTED |
| `/api/v2` routing | NOT YET IMPLEMENTED |
| route registration | NOT YET IMPLEMENTED |
| dependency injection | NOT YET IMPLEMENTED |
| authentication dependency | NOT YET IMPLEMENTED |
| authorization dependency | BLOCKED BY MISSING CONTRACT |
| application use-case invocation | NOT YET IMPLEMENTED |
| request/response schemas | NOT YET IMPLEMENTED |
| patient DTO boundary | NOT YET IMPLEMENTED |
| DTO → usage boundary | NOT YET IMPLEMENTED |
| exception handlers | NOT YET IMPLEMENTED |
| health/readiness endpoints | NOT YET IMPLEMENTED |
| OpenAPI contract | NOT YET IMPLEMENTED |
| API versioning | PARTIALLY IMPLEMENTED (v2 dir exists; no route) |

---

## 9. Application-boundary analysis

Per-operation wiring `HTTP → schema → security context → authz → command →
UoW → domain/infra`:

- **Every** arrow after the verifier is absent: no schema, no authz dependency,
  no command invocation from HTTP, no UoW tenant binding at the boundary, no
  domain/infra call from a route.
- **No route directly touches SQLAlchemy/PostgreSQL/Redis/S3/ORM** — but that
  is because there *are no routes*, not because the boundary correctly
  forbids it.

---

## 10. Idempotency analysis — BLOCKED BY MISSING CONTRACT

- No `IdempotencyKey`, no replay store, no dedup store, no idempotency port.
- The whatsapp boundary **correctly** hints that replay protection is delegated
  to a calling store ("idempotency are delegated to the dedup store in the
  calling boundary") — but that store has **no contract yet**.
- Minimum contracts: `IdempotencyStore`/`ReplayStore` port with
  `reserve(key, tenant_id, actor)` + `get/set`, HTTP `Idempotency-Key` header
  schema, tenant-scoped.

---

## 11. Rate-limiting analysis — BLOCKED BY MISSING CONTRACT

- No rate-limit port, no Redis rate-limit adapter, no key strategy, no
  per-tenant/user/IP scoping, no retry semantics, no whatsapp-specific
  pacing. Not implemented; not representable from current contracts.

---

## 12. WhatsApp analysis

Verbatim from the whatsapp boundary:

| Item | Status |
| :-- | :-- |
| A signature verification (`X-Hub-Signature-256`) | IMPLEMENTED |
| B verify-token handshake | IMPLEMENTED |
| C raw-body protection (HMAC over raw bytes) | IMPLEMENTED |
| D neutral envelope (PHI-minimal) | IMPLEMENTED |
| E message normalization | IMPLEMENTED |
| F replay protection | BLOCKED BY MISSING CONTRACT (delegated store absent) |
| G deduplication | BLOCKED BY MISSING CONTRACT (store absent) |
| H application invocation | NOT YET IMPLEMENTED (no handler wired) |
| I asynchronous processing | NOT YET IMPLEMENTED (no queue/boundary) |

---

## 13. Audit / logging analysis

| Concern | Status |
| :-- | :-- |
| correlation ID | NOT YET IMPLEMENTED (no HTTP boundary to mint one) |
| authenticated actor | BLOCKED (no principal type) |
| tenant | PARTIALLY IMPLEMENTED (claim + RLS; no audit) |
| operation / target / audit event | NOT YET IMPLEMENTED (no audit port) |
| `InfrastructureLogger` | IMPLEMENTED (Gate 05 logging infra) |
| PHI redaction | IMPLEMENTED (`logging` redaction primitives) |
| secret redaction | IMPLEMENTED (whatsapp signatures never logged; verification over raw body) |

**Separations kept:** audit events (would be new), domain events (Gate 03/04
exist), system telemetry (logging infra), channel telemetry (webhooks as
neutral envelope). They are **not** merged — no audit event mechanism exists
to merge into.

---

## 14. HTTP security analysis

| Concern | Status |
| :-- | :-- |
| CORS | NOT YET IMPLEMENTED (no app) |
| security headers | NOT YET IMPLEMENTED |
| request-size limits | NOT YET IMPLEMENTED |
| malformed request handling | PARTIALLY IMPLEMENTED (verifier handles malformed tokens/bodies) |
| authentication error handling | PARTIALLY IMPLEMENTED (verifier errors typed; no HTTP mapping) |
| authorization error handling | BLOCKED (no authz) |
| safe 500 / strace suppression | NOT YET IMPLEMENTED |
| OpenAPI exposure policy | NOT YET IMPLEMENTED |

---

## 15. Security test coverage

- **17 security tests** (7 HS256 JWT + 10 WhatsApp webhook) — all green,
  counting **verifier/crypto** units only.
- **Not implemented tests (matrix-only, not counted as implemented):**
  RBAC per-role allow/deny (blocked), relationship allow/deny (blocked),
  tenant RLS propagation from JWT, replay/idempotency, rate-limit, audit,
  patient-self, OpenAPI/cors/errorhandler. These are **not** present as tests.

---

## 16. Missing-contract catalog (minimum new contracts)

| Contract | Owned by | Minimum capability | Consumer | Later adapter | Security significance | Requires Gate 03 invariants change? |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| 1. `AuthenticatedContext` (principal + tenant) | application ports | `resolved via an AuthenticatingContext` (actor id, tenant_id, roles, facility_id) | sub use-cases/HTTP boundary | token→context adapter (HS256/Keycloak) | Basis for every authz decision | No |
| 2. `CaregiverRelationshipRepository` (port) | application ports | `find_for_caregiver`, `find_for_patient`, `is_relationship_active` (tenant-scoped) | relationship authz use case | RLS-backed RDBMS adapter | Caregiver per-patient allow/deny | No |
| 3. `IdentityPatientMappingPort` | application ports | resolve `(tenant, phone/identity) → patient_id`, phone claim contract | patient self-access | claims+repository adapter | Patient own-record access | No |
| 4. `IdempotencyStore` (port) + `Idempotency-Key` schema | application ports / http schema | `claim/get/set` tenant-scoped key→result; replay/idempotency boundary | webhooks + all POST boundary | Redis/RDBMS adapter | Replay/idempotency | No |
| 5. `RateLimiter` port | application ports | `allow(key), refill/consume` per tenant/user/IP scope | HTTP middleware | Redis adapter | DoS/brute-force | No |
| 6. `AuditStore` port + `AuditEvent` | application ports | append event (correlation, actor, tenant, op, target); PHI-redacted | HTTP boundary; use cases | RDBMS adapter | Observability/compliance/forensics | No |
| 7. HTTP DI + route boundary (routers, deps, error handlers, app factory) | interfaces/http | wire schema→authz→usecase→UoW | whole API | FastAPI router module | Everything HTTP | No |
| 8. Role→permission `AuthorizationPolicy` port/contract | application ports | `authorize(actor, operation)` per role+facility; deny-by-default | HTTP boundary + use cases | policy module + RLS backstop | RBAC / relationship / tenant authz | No |

Every contract is **additive to ports**; none changes Gate 03 (`CaregiverRelationship`
and `CareTeamMember` entities already carry the required relation/role primitives).

---

## 17. Gate placement recommendations

| Missing capability | Recommended gate |
| :-- | :-- |
| HTTP boundary (routers, DI, app factory, deps, error handlers, OpenAPI, health) | **DEDICATED Gate 07 — HTTP transport/DI boundary** |
| RBAC + role→permission `AuthorizationPolicy` (policy module, no per-patient claim PLEX contract) | **Gate 07 (with HTTP)** or **Gate 08** if split |
| Relationship-aware per-patient authorization (needs `CaregiverRelationshipRepository` port) | **Contract + Gate 09 / dedicated** — do NOT fold into Gate 07 security |
| Identity→patient persona bridge (`IdentityPatientMappingPort` + phone claim) | **Contract Gate** (patient persona contract) |
| Idempotency / replay store | **Dedicated idempotency gate** (or Gate 07 with HTTP if contract-first) |
| Rate limiting | **Dedicated infrastructure gate** (Redis adapter) |
| Audit (events, correlation, actor, tenant) | **Dedicated observability gate** |

**Do not push everything into Gate 07** — contract-carrying authz/identity
items are their own gates.

---

## 18. Risk matrix

| Risk | Severity | Classification basis |
| :-- | :-- | :-- |
| Cross-tenant access via un-wired RLS (if routes were added today without bound tenant) | CRITICAL | RLS exists but no JWT→UoW binding; a future route that forgets the binding = tenant-wide |
| Per-patient caregiver cross-access | CRITICAL | `CaregiverRelationship` has no repository/RLS → enforced allow/deny impossible; must remain deny-by-default until contract exists |
| Patient identity confusion (self vs clinician vs caregiver) | CRITICAL | No `IdentityPatientMappingPort` / claim bridge → cannot prove "this actor == patient X" |
| Webhook replay / forged-then-replayed inbound event | HIGH | Replay delegated to a store that has no contract → replay protection absent |
| Missing rate limits on auth/verify endpoints | HIGH | brute-force on verify-token / HS256 secret keypath |
| Missing audit trail | MEDIUM | no AuditEvent/port → no forensics, no PHI access review |
| Missing OpenAPI/security headers/CORS policy | MEDIUM | no app; when app ships, must enforce |
| Constant-time/raw-body crypto regression | LOW → HIGH if lapsed | verifier is correct today; must stay guarded by tests |

---

## 19. What is already safe and reusable

- Stdlib-only JWT HS256 + `X-Hub-Signature-256` verifiers, constant-time,
  raw-body byte-exact, deterministic serialization. **Fully reusable** as the
  crypto core of the future HTTP boundary.
- WhatsApp neutral envelope — PHI-minimal, channel-clean; reusable boundary.
- Gate 05 RLS primitive (`set_config('app.current_tenant_id')` + RLS policy)
  — the tenant **mechanism** the future HTTP boundary must wire to.
- PHI/secret redaction in logging infra.
- Role normalization (`roles.py`) — canonical allow-set of `CareTeamRole`.
- 17 verifier/security tests as a regression lock on the crypto core.

---

## 20. What MUST NOT be implemented as a shortcut

- ❌ "role=doctor ⇒ access any patient" — violates relationship-aware deny.
- ❌ "caregiver ⇒ access all patients" — no allow; must be relationship store.
- ❌ "patient ⇒ any patient_id" — must go through IdentityPatientMappingPort.
- ❌ "trust a decoded-but-unverified token claim `patient_id`".
- ❌ "invent an admin bypass / `is_superuser` escape hatch".
- ❌ "bolt rate-limit/replay onto the verifier" — separate ports.
- ❌ "mark Gate 06 complete because crypto works" — the HTTP+authz slice is not
  complete.

---

## 21. Recommended next sequence

1. **Gate 07 (JSON contract):** `AuthenticatedContext`, roles→permission
   `AuthorizationPolicy` (deny-by-default), HTTP DI + route boundary
   (routers/deps/app/error-handlers/OpenAPI/health/versioning), wire
   JWT→UoW tenant binding to Gate 05 RLS, rate-limit port + Redis adapter,
   idempotency store port + `Idempotency-Key`, audit port + `AuditEvent`,
   security headers/CORS/size-limits, `IdentityPatientMappingPort` contract.
2. **Contract-then-implement for per-patient relationship + identity persona:**
   `CaregiverRelationshipRepository` port + RLS, phone-claim contract, then
   the relationship/self authz use cases.
3. Re-run the full 36-matrix — items 1-17 stay green; 18-36 become measurable.

(Sequence is a *recommendation*; each gate must be formally approved.)

---

## 22. Explicit statement — Gate 07 LOCKED

Gate 07 is **locked**. This analysis does not start, stage, or implement Gate 07.
Nothing here is a commit, a tag, or a migration.

STOP.

---

*Analysis date: 2026 — Gate 06 completion-gap audit. Tree untouched; the only
file created by this audit is this document.*
