# Gate 10C-R — Keycloak RS256 / JWKS Trust Boundary

**Status:** IMPLEMENTATION COMPLETE — GATE 10C-R READY FOR AUDIT
**Scope:** FastAPI backend authentication trust boundary (no mobile, no DB schema, no Gate 08/09 behavior change, no tenant/RLS semantics change, no Keycloak server change).

---

## 1. Current problem

Before Gate 10C-R, the backend verified JWTs with a hard-coded HS256 path:

- `backend/interfaces/http/v2/security/jwt.py` — stdlib-only `verify_hs256(token, secret)` constant-time HMAC; rejected any non-HS256 `alg`.
- `config/settings.py IdentityConfig` — `client_secret` doubled as the HMAC signing secret.
- The HTTP dependency (`dependencies.get_verified_claims`) had **no audience validation** and no `kid`-based key handling; production Keycloak RS256 tokens would have been rejected.
- The idempotency middleware (`ops/idempotency.py`) kept a **second, independent** HS256 verification path (`_safe_claims`).

There was therefore no production path to verify Keycloak-issued RS256 access tokens.

## 2. Trust model (target chain)

```
Keycloak  ── signs ──►  RS256 JWT (kid, iss, aud=thali-backend, sub, tenant_id, realm_access.roles)
                            │
                            ▼
                  algorithm allow-list (RS256 default)
                            │
                            ▼
              OIDC discovery / explicit jwks_uri ──► JWKS document
                            │
                     kid-based key selection
                     (in-process TTL cache, refresh-once on unknown kid)
                            │
                            ▼
              signature verification (verify_rs256 → PyJWT, allow-list only)
                            │
            issuer (configured) + audience (client_id) + exp validation
                            │
                            ▼
                    trusted claims
                    ├─► AuthenticatedContext (actor_id, tenant_id, roles, facility_id)
                    └─► Gate 08 AuthorizationPolicy
                            │
                            ▼
              tenant_id → SqlAlchemyUnitOfWork → set_config('app.current_tenant_id')
                            │
                            ▼
                   PostgreSQL Row Level Security
```

## 3. JWKS architecture

New module `backend/interfaces/http/v2/security/jwks.py` — `JwksClient`:

- **Discovery first:** with no explicit `THALI_IDENTITY__JWKS_URI`, the client fetches `{issuer_url}/.well-known/openid-configuration` and uses the advertised `jwks_uri`. It **never constructs the JWKS URL by guesswork**.
- **Explicit override:** `THALI_IDENTITY__JWKS_URI`, when set, wins outright and skips discovery.
- **Caching:** the resolved `jwks_uri` and the fetched keys document are cached in-process with a default 300s TTL; verification does not hit the network per request.
- **`kid` selection:** signing keys are indexed by `kid` (RFC 7517). Only `kty=RSA`, `use=sig` (or no `use`) keys are loaded; encryption keys are ignored.
- **Rotation:** an unknown `kid` triggers exactly **one** cache refresh and retry. If the key still cannot be found, or the refresh fails, the request **fails closed**.
- **Failure behavior:** discovery/JWKS fetch failure, missing `jwks_uri`, empty keys, or unusable keys all raise `JwtSignatureError` → mapped to 401. No HS256 fallback ever.

## 4. Issuer validation

`verify_access_token` checks `iss` against the configured `THALI_IDENTITY__ISSUER_URL`. This is enforced for both the RS256 path (PyJWT `issuer=` option) and the HS256 path (manual check), and never trusts the token's own declared issuer blindly.

## 5. Audience validation

Expected audience = the configured backend client/resource identifier, `settings.identity.client_id` (`thali-backend` in `.env.example`). It is enforced for **both** paths (PyJWT `audience=` for RS256; manual list-aware check for HS256). String or list audiences containing `client_id` are accepted; anything else is rejected with 401. **Audience validation is never skipped** — an unconfigured audience makes authentication fail closed (`audience is not configured`). The mobile client ID is not used as the backend audience.

## 6. Algorithm policy

- Default: `THALI_IDENTITY__ALLOWED_ALGORITHMS=RS256` (in `IdentityConfig.allowed_algorithms`).
- The allow-list is parsed from configuration; a token's `alg` claim must be in the list.
- HS256 exists only as an **explicit development/testing override** (e.g. `THALI_IDENTITY__ALLOWED_ALGORITHMS=HS256`). It is never auto-detected from the environment, and production never accepts HS256 merely because tests use it.
- Algorithm-confusion attempts (an HS256 token presented under an RS256 policy) are rejected.

## 7. Key rotation

Covered by `ten` unit tests in `tests/security/test_jwt_rs256.py`:

- current kid verifies from cache;
- new kid found after exactly one refresh (success);
- unknown kid after refresh → fail closed;
- expired cache → transparent refetch;
- refresh failure / JWKS downtime → fail closed;
- encryption-use keys ignored; empty keys → fail closed.

## 8. Error handling / safe failures

All authentication errors are safe messages (`TokenVerificationError` with fixed strings, or `JwtSignatureError` mapped to 401): no JWT contents, signing keys, JWKS payloads, stack traces, internal crypto exceptions, or configuration secrets are ever returned or logged. `tests/api/test_auth_rs256.py` asserts 401 bodies do not contain the secret, issuer, token segment, or signature.

## 9. Development/test compatibility (HS256 isolation)

- `tests/api/conftest.py` explicitly sets `THALI_IDENTITY__ALLOWED_ALGORITHMS=HS256` **and** `THALI_IDENTITY__CLIENT_ID` for legacy HS256 boundary tests; `make_jwt` now emits an `aud` claim by default.
- New RS256 suites explicitly override to `RS256` + a fake JWKS endpoint.
- Default (unset) policy is asserted to be `RS256`.
- The idempotency middleware (`ops/idempotency.py`) now delegates `_safe_claims` to the same `dependencies.verify_access_token` used by the HTTP boundary — there is **no independent legacy HS256 path** (mandated correction #1).

## 10. Dependencies

`requirements.txt` adds `PyJWT>=2.9` and `cryptography>=43.0`. PyJWT performs RS256 signature verification over cryptography RSA keys; the JWKS client uses bundled `httpx`.

## 11. Gate 08 authorization / Gate 09 operational regressions — unchanged

- `AuthorizationPolicy`, `DefaultAuthorizationPolicy`, `RelationshipAuthorizationPolicy` (Gate 08) are untouched; the full relational-identity suite still passes.
- Idempotency, replay/dedup, rate limiting, audit, outbox, channel orchestration, and correlation IDs (Gate 09) are untouched; `_safe_claims` semantics preserved (valid token → tenant/actor scoping; invalid → pass-through 401).
- Tenant/RLS semantics unchanged — `AuthenticatedContext.tenant_id → UnitOfWork → SET LOCAL app.current_tenant_id → RLS`. Proven on live PostgreSQL for both HS256 (existing) and RS256 (new `TestHTTPToRLSChainRs256`).

## 12. Security test matrix

| Case | Result |
|---|---|
| valid RS256 (JWKS) → 200 + correct context | passing (unit + HTTP + live-PG RLS) |
| expired RS256 | 401 |
| invalid RS256 signature | 401 |
| wrong issuer | 401 |
| wrong audience | 401 |
| audience list containing client_id | 200 |
| missing subject | 401 |
| missing / malformed tenant_id | 401 |
| HS256 under RS256-only policy | 401 |
| alg=none / unsupported alg | 401 |
| unknown kid (cached + refresh) | 401, fail closed |
| key rotation (new kid after refresh) | 200 |
| JWKS unavailable | 401, fail closed |
| malformed token | 401 |
| tampered payload | 401 |
| idempotency uses same policy (RS256 + HS256) | covered |
| secrets / token contents not leaked in 401 | covered |
| default algorithm policy = RS256 | covered |

Full pytest: **488 passed** (436 baseline + 52 new). Architecture import audit: extended allow-list with `jwt`/`cryptography`/`httpx`; all http modules importable, no circular imports.

## 13. Gate 10C relationship

Gate 10C (mobile OIDC shell, commit `8efddae`) requires the backend to trust Keycloak RS256 tokens; Gate 10C-R supplies that backend trust boundary. Mobile is unchanged in this gate.

## 14. External Keycloak provisioning requirements (no server changes made here)

- Realm `thali` with **OIDC** enabled, issuer `http://localhost:8080/realms/thali` in dev (production HTTPS URL).
- Backend client `thali-backend` configured as a public client for the mobile app; the **backend resource/audience** used for access-token audience is `thali-backend`.
- Access tokens signed with `RS256`; realm requires an RSA signing key published at
  `{issuer}/.well-known/openid-configuration → jwks_uri` at
  `{issuer}/protocol/openid-connect/certs`.
- Claims contract: `sub` (Keycloak subject UUID), `iss`, `aud` (contains `thali-backend`), `exp` (required), `tenant_id` (UUID, custom mapper), `realm_access.roles` (role tokens e.g. `doctor`/`admin`/`nurse`/`patient`), `preferred_username`.
- Backend deployment sets `THALI_IDENTITY__ISSUER_URL`, `THALI_IDENTITY__CLIENT_ID=thali-backend`, and either `THALI_IDENTITY__JWKS_URI` or relies on discovery; `THALI_IDENTITY__ALLOWED_ALGORITHMS=RS256`.