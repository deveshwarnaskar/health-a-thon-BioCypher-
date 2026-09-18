# Gate 10C-R Implementation Plan: Keycloak RS256/JWKS Trust Boundary

## Overview

Upgrade the FastAPI backend from HS256-only JWT verification to RS256 + JWKS for production Keycloak OIDC tokens. Maintain HS256 as a dev/test-only path via environment-switched algorithm policy.

## Architecture

### Verification Flow

```
Authorization: Bearer <token>
  → parse header → get kid + alg
  → check alg against allow-list (env-configured)
  → if RS256:
      → JWKS client: fetch/cache JWKS → find key by kid → RSA public key
      → verify RS256 signature using PyJWT
  → if HS256:
      → verify HS256 using existing stdlib code + shared secret
  → validate: exp, iss (against configured issuer), aud (against client_id), sub (required), tenant_id (required + UUID)
  → AuthenticatedContext
```

### Configuration

New env vars in `config/settings.py` `IdentityConfig`:
- `allowed_algorithms: str` — comma-separated, default `"RS256"` for prod, `"HS256"` for tests
- `jwks_uri: str` — JWKS endpoint URL, default `{issuer_url}/protocol/openid-connect/certs`

Existing fields reused:
- `issuer_url` — already validated in `dependencies.py`
- `client_id` — used as expected audience (new: aud validation added)
- `client_secret` — still used as HMAC secret for HS256 path AND idempotency fingerprinting

### Backward Compatibility

- **Production**: `THALI_IDENTITY__ALLOWED_ALGORITHMS=RS256` — only RS256 accepted
- **Tests**: `THALI_IDENTITY__ALLOWED_ALGORITHMS=HS256` — existing HS256 tests pass unchanged
- **Idempotency middleware**: No changes needed — it uses HMAC for fingerprinting (not JWT verification), and the `_safe_claims()` method will use the same dual-path verifier

## Files to Modify

### 1. `requirements.txt` — Add PyJWT + cryptography

```
PyJWT>=2.9
cryptography>=43.0
```

PyJWT handles RS256 verification natively. `cryptography` provides RSA key parsing.

### 2. `config/settings.py` — Add JWKS/audience/algorithm settings

Add to `IdentityConfig`:
```python
allowed_algorithms: str = Field(default="RS256", description="comma-separated allowed JWT algorithms")
jwks_uri: str = Field(default="", description="JWKS endpoint URL (defaults to issuer_url/protocol/openid-connect/certs)")
audience: str = Field(default="", description="expected JWT audience (defaults to client_id)")
```

### 3. `backend/interfaces/http/v2/security/jwt.py` — Add RS256 verifier

Add `verify_rs256(token, public_key, algorithms, audience, issuer)` alongside existing `verify_hs256`.

The new function:
- Uses `jwt.decode(token, key, algorithms=[...], audience=..., issuer=...)` from PyJWT
- Validates: signature, algorithm allow-list, exp, aud, iss
- Returns same `Hs256Result`-shaped dataclass (renamed to `VerifiedToken` for generality)
- Raises `JwtSignatureError` on any failure (same error class)
- Does NOT log JWT contents, signing keys, or JWKS payload

### 4. `backend/interfaces/http/v2/security/jwks.py` — New JWKS client

Simple JWKS fetcher with:
- `JwksClient(jwks_uri, fetch_fn)` — injectable fetch for tests
- `get_signing_key(token)` → `jwt.algorithms.RSAAlgorithm` public key
- Kid-based key lookup
- Thread-safe caching with TTL
- On unknown kid → force JWKS refresh once → retry
- On JWKS failure → raise `JwtSignatureError` (fail closed)

### 5. `backend/interfaces/http/dependencies.py` — Dual-path verification

Modify `get_verified_claims()`:
- Parse token header to get `kid` and `alg`
- Check `alg` against `allowed_algorithms` from config
- If RS256 → JWKS path → PyJWT verify
- If HS256 → existing path → stdlib verify
- Add audience validation (check `aud` claim against configured audience)
- All existing exp/iss/sub/tenant_id checks remain

### 6. `backend/interfaces/http/ops/idempotency.py` — Update `_safe_claims()`

Change from direct `verify_hs256()` call to use the same dual-path verifier from dependencies. The idempotency middleware doesn't need full audience validation (it just extracts sub/tenant), but it should respect the algorithm policy.

### 7. `backend/interfaces/http/v2/security/__init__.py` — Export new symbols

Export `VerifiedToken`, `verify_rs256`, `JwksClient`.

### 8. `backend/interfaces/http/app.py` — Update OpenAPI description

Change bearer auth description from "HS256 JWT" to "RS256/HS256 JWT".

### 9. `tests/api/conftest.py` — Add RS256 test token builder

Add `make_rs256_jwt()` function using a test RSA key pair:
- Generate RSA key pair once (module-level)
- Build JWT with RS256 signature using PyJWT
- Same interface as existing `make_jwt()` for easy switching

Override `THALI_IDENTITY__ALLOWED_ALGORITHMS=HS256` in test config (existing tests keep working).

### 10. `tests/api/test_auth.py` — Add RS256 auth tests

Add tests for the RS256 path:
- Valid RS256 token → 200
- RS256 with wrong audience → 401
- RS256 with wrong issuer → 401
- RS256 with expired token → 401
- RS256 with invalid signature → 401
- RS256 with unknown kid → 401
- HS256 token when RS256-only policy → 401
- RS256 token when HS256-only policy → 401

### 11. `tests/security/test_jwt_rs256.py` — RS256 crypto boundary tests

Standalone RS256 verification tests (parallel to `test_jwt_hs256_signature.py`):
- Valid RS256 token acceptance
- Tampered payload rejection
- Wrong key rejection
- Algorithm confusion rejection (HS256 token sent with RS256 key)
- Unknown kid handling
- JWKS refresh after rotation
- JWKS unavailable fails closed
- Malformed JWT rejection

### 12. `.env.example` — Document new env vars

Add `THALI_IDENTITY__ALLOWED_ALGORITHMS`, `THALI_IDENTITY__JWKS_URI`, `THALI_IDENTITY__AUDIENCE`.

## Test Matrix (21 items)

| # | Test | Path |
|---|---|---|
| 1 | Valid RS256 token | test_auth.py / test_jwt_rs256.py |
| 2 | Expired token | test_auth.py / test_jwt_rs256.py |
| 3 | Invalid RS256 signature | test_jwt_rs256.py |
| 4 | Wrong issuer | test_auth.py / test_jwt_rs256.py |
| 5 | Wrong audience | test_auth.py / test_jwt_rs256.py |
| 6 | Missing sub | test_auth.py / test_jwt_rs256.py |
| 7 | Malformed sub | test_auth.py |
| 8 | Missing tenant_id | test_auth.py |
| 9 | Malformed tenant_id | test_auth.py |
| 10 | Unsupported HS256 token (RS256-only policy) | test_auth.py |
| 11 | Unsupported algorithm in header | test_jwt_rs256.py |
| 12 | Unknown kid | test_jwt_rs256.py |
| 13 | JWKS refresh after key rotation | test_jwt_rs256.py |
| 14 | JWKS unavailable | test_jwt_rs256.py |
| 15 | Malformed JWT | test_auth.py / test_jwt_rs256.py |
| 16 | Tampered JWT | test_jwt_rs256.py |
| 17 | Valid token preserves AuthenticatedContext | test_auth.py |
| 18 | Valid token preserves tenant RLS | test_tenant_http.py (existing) |
| 19 | Cross-tenant isolation denied | test_tenant_http.py (existing) |
| 20 | Gate 08 authorization regression | test_gate_08_relational_identity.py (existing) |
| 21 | Gate 09 regression | test_gate_09_ops_api.py (existing) |

## Security Checklist

- [x] Production Keycloak tokens are RS256 (algorithm policy default)
- [x] JWKS signature verification mandatory (PyJWT)
- [x] Algorithm allow-list (env-configured)
- [x] Issuer validation (existing + preserved)
- [x] Audience validation (new: against client_id)
- [x] Expiration validation (existing + preserved)
- [x] kid handling (JWKS client)
- [x] Key rotation support (JWKS refresh on unknown kid)
- [x] JWKS failure fails closed
- [x] No HS256 production fallback (env default is RS256)
- [x] No signing secrets in client
- [x] No signing keys in logs
- [x] No JWT contents in logs
- [x] No PHI in logs

## What Does NOT Change

- `AuthenticatedContext` — frozen dataclass, same fields
- `AuthorizationPolicy` / `RelationshipAuthorizationPolicy` — Gate 08 unchanged
- `role_tokens()` — same normalization
- Tenant → UnitOfWork → RLS chain — unchanged
- All Gate 08/09 behavior — untouched
- Mobile app — zero changes
- Database migrations — none
- Keycloak server config — documented only
