# GATE 06 — API + Security Boundary

**THALI × P.L.A.T.E. Production Program — Gate 06: verified inbound boundary
and stdlib-only API security**

- **Status:** PASS (implementable scope) with 3 items explicitly declared
  **NOT-IMPLEMENTED** (see §10) — no dangerous authorization shortcut was
  invented
- **Branch:** `feature/gate-06-api-security`
- **Gate 05 (predecessor):** `5503ad0` / `gate-05-infrastructure-adapters-complete`
- **Gate 06 migration doc (this file):** `docs/migration/GATE_06_API_SECURITY.md`

---

## 1. Gate objective

Establish the **API + security boundary** on top of the Gate 04/05 application
layer, as a set of thin HTTP adapters that:

1. put cryptographic signature verification *before* any body is parsed or
   trusted (JWT HS256 + WhatsApp `X-Hub-Signature-256`);
2. normalize a verified provider event into a **neutral, PHI-minimal inbound
   envelope** — the webhook channel never embeds domain entities or clinical
   business rules;
3. enforce the boundary as **role + relationship-aware**, using already
   representable Gate 04/05 contracts (facility `id`, tenant, JWT roles) and
   explicitly refusing to invent any persistence or claim bridge that does not
   exist yet.

No new dependency is added (`requirements.txt` is untouched): JWT HS256
verification and WhatsApp signature verification use **only the standard
library** (`hmac`, `hashlib`, `base64`, `secrets`, `datetime`).

## 2. Starting commit/tag

Predecessor gate checkpoint (unchanged):

| Item | Value |
| :-- | :-- |
| Gate 05 commit | `5503ad0` |
| Gate 05 tag | `gate-05-infrastructure-adapters-complete` |
| Gate 05 test baseline | 209 (all passing, verified at Gate 05 close) |

Gate 06 starts from that checkpoint and is **additive only** — it creates new
boundary files under `interfaces/http/v2/` and new tests under `tests/security/`
and touches none of the legacy `app/server` surface.

## 3. Files created (Gate 06, this gate)

Boundary — JWT signature verification (stdlib only):

- `backend/interfaces/http/v2/security/__init__.py` — package root exports:
  `Hs256Result`, `JwtSignatureError`, `verify_hs256`, `role_tokens`
- `backend/interfaces/http/v2/security/constants.py` — HS256 domain constants
  (`alg` claim constants, algorithm allow-list)
- `backend/interfaces/http/v2/security/jwt.py` — `verify_hs256`
  implementation: header parse → `alg` allow-list (`HS256` only; `alg=none` and
  any other alg rejected) → constant-time HMAC-SHA256 over the exact signature
  input (`b64(header).b64(payload)`) → `Hs256Result`
- `backend/interfaces/http/v2/security/roles.py` — realm-role token
  normalization into the application role enum used by Gate 04 use cases

Boundary — WhatsApp webhook (inbound, verified):

- `backend/interfaces/http/v2/webhooks/whatsapp/__init__.py` — adapter root
  exports `WhatsAppInboundEnvelope`, `verify_x_hub_signature_256`,
  `challenge_response`
- `backend/interfaces/http/v2/webhooks/whatsapp/envelope.py` —
  `WhatsAppInboundEnvelope`: neutral envelope normalizing a verified inbound
  event to `<message_id, source_phone, event_type, timestamp>` only — **no PHI
  in the envelope**
- `backend/interfaces/http/v2/webhooks/whatsapp/signature.py` —
  `verify_x_hub_signature_256` (HMAC-SHA256 over the raw body bytes, constant
  time) + `WebhookSignatureError`
- `backend/interfaces/http/v2/webhooks/whatsapp/verify_token.py` —
  `challenge_response` (verify-token handshake, constant-time token compare)
  + `VerifyTokenError`

Tests (this gate, one file per boundary):

- `tests/security/test_jwt_hs256_signature.py` — 7 tests
- `tests/security/test_whatsapp_webhook.py` — 10 tests

## 4. Files modified / deleted

- **Modified (0):** none. Gate 06 is additive; no existing file changed, no
  legacy surface touched.
- **Deleted (0):** none.
- **`requirements.txt`: unchanged** — no new dependency (stdlib-only crypto).

## 5. API boundary architecture

```
client ─▶ http/v2 (new "v2" http boundary ── placeholder contract)
            ├─ security/         HS256-whatsapp + JWT signature verification (stdlib)
            │    └─ jwt.py, signature… (via webhooks/whatsapp/signature)
            └─ webhooks/whatsapp/  verified inbound channel adapter
```

The boundary is a **thin adapter**: for the implementable scope it performs
(1) cryptographic verification, (2) provider-event normalization into a
neutral envelope, and (3) constant-time handshake/compare. It contains **no**
SQL and **no** domain-entity imports in the envelope; envelope fields are
primitive (str + naive/zoned timestamp).

## 6. Security boundary — JWT HS256 (stdlib-only)

`backend/interfaces/http/v2/security/jwt.py::verify_hs256`:

- decodes **exactly two** base64url segments + signature (three segments total);
  rejects anything else as malformed;
- enforces `alg == "HS256"` from an allow-list constant; **`alg=none` is
  rejected** — unsigned JWTs are never accepted;
- recomputes `HMAC-SHA256(secret, b64(header).b64(payload))` and compares with
  **`hmac.compare_digest`** (constant time);
- returns a frozen `Hs256Result`; raises `JwtSignatureError` on any mismatch,
  tampering, malformed structure, or wrong secret.

This implements matrix items **1–7** (valid / tampered payload / wrong secret /
unsupported alg / malformed base64 / wrong-key / alg-none) — all tested.

## 7. WhatsApp webhook boundary

`signature.verify_x_hub_signature_256(raw_body, header, secret)`:

- verifies `X-Hub-Signature-256` (HMAC-SHA256) over the **raw body bytes** —
  the body is never re-serialized or parsed before verification;
- requires the `sha256=` prefix, constant-time compare, `WebhookSignatureError`
  on missing/empty/wrong-prefix/tampered/wrong-secret.

`verify_token.challenge_response(...)`:

- echoes the `hub.challenge` string **only** when verify token matches and mode
  is authorizable; constant-time compare; `VerifyTokenError` on mismatch or
  unsupported mode. This implements the protected GET handshake.

## 8. Security test matrix — implementable scope (PASS)

| # | Item | Status | Test |
| :-- | :-- | :-- | :-- |
| 1 | HS256: valid token accepted | ✅ | `test_verify_hs256_accepts_a_valid_token` |
| 2 | HS256: tampered payload rejected | ✅ | `test_verify_hs256_rejects_a_tampered_payload` |
| 3 | HS256: wrong secret rejected | ✅ | `test_verify_hs256_rejects_a_wrong_secret` |
| 4 | HS256: `alg=none` / unsupported alg rejected | ✅ | `test_verify_hs256_rejects_unsupported_alg` |
| 5 | HS256: malformed base64 / structure rejected | ✅ | `test_verify_hs256_rejects_malformed_token_structures` |
| 6 | HS256: empty secret path rejected | ✅ | `test_verify_hs256_rejects_empty_secret_path` |
| 7 | HS256: signature input serialized deterministically | ✅ | `test_verify_hs256_serializes_fields_deterministically` |
| 8 | Webhook: valid `X-Hub-Signature-256` accepted | ✅ | `test_verify_x_hub_signature_256_accepts_valid_signature` |
| 9 | Webhook: tampered body rejected | ✅ | `test_verify_x_hub_signature_256_rejects_tampered_body` |
| 10 | Webhook: wrong secret rejected | ✅ | `test_verify_x_hub_signature_256_rejects_wrong_secret` |
| 11 | Webhook: missing header rejected | ✅ | `test_verify_x_hub_signature_256_rejects_missing_header` |
| 12 | Webhook: empty header rejected | ✅ | `test_verify_x_hub_signature_256_rejects_empty_header` |
| 13 | Webhook: wrong `sha256=` prefix rejected | ✅ | `test_verify_x_hub_signature_256_rejects_wrong_prefix` |
| 14 | Handshake: valid verify-token echoes challenge | ✅ | `test_challenge_response_echoes_challenge_for_valid_handshake` |
| 15 | Handshake: token mismatch rejected | ✅ | `test_challenge_response_rejects_token_mismatch` |
| 16 | Handshake: unsupported mode rejected | ✅ | `test_challenge_response_rejects_unsupported_mode` |
| 17 | Envelope: verified inbound event normalized (PHI-minimal) | ✅ | `test_envelope_normalizes_verified_inbound_event` |

**17 implementable matrix items — ALL tested and green.**

## 9. Test results (Gate 06 suite)

```
247.whatsapp … 10 passed
jwt hs256 … 7 passed
tests/security: 17 passed
FULL SUITE: 226 passed
```

## 10. NOT-IMPLEMENTED — exact missing contracts (STOP-guarded)

The rule for Gate 06: *if a security dimension is not representable by the
approved Gate 04/05 contracts, do **not** invent a dangerous authorization
shortcut — instead report the exact missing contract.* Three items are not
implementable. Their exit-criteria checkboxes are **unchecked** and they are
**not** faked as passing.

| # | Item | Missing contract (exact) | Why not implementable today |
| :-- | :-- | :-- | :-- |
| A | **Per-patient caregiver relationship authorization** | A persisted + queryable `CaregiverRelationship` link (caregiver ↔ patient) with a domain repository port, plus an RLS/persistence path. | Gate 04/05 expose the `CaregiverRelationship` **domain entity only** — unpersisted, **no repository port**, no RLS path, no verified caregiver↔patient record. Implementing per-patient caregiver allow-lists now would require inventing a persistence contract that does not exist. |
| B | **Patient "own-records" self-access** | A verified identity↔patient bridge (e.g. a JWT phone/subject claim that maps to the patient persona) provided by the identity boundary. | No such claim bridge exists in the jwt/identity contract; there is no safe way to prove "this caller IS patient X" today. Listing it as passing would be a false claim. |
| C | **Webhook replay / idempotency store** | A dedup/idempotency store (provider message-id keyed) at the webhook boundary. | The whatsapp adapter currently verifies-then-envelopes; replay protection is a boundary-level store that is explicitly deferred. Introducing real "replay-protected" acceptance without that store would be an unusable claimed guarantee. |

These are deliberately **reported, not faked**. The exact missing contracts are
(A) a persisted+queryable `CaregiverRelationship` repository port + RLS path,
(B) a JWT identity→patient claim bridge, and (C) a webhook dedup store.

## 11. Import / dependency discipline

- `requirements.txt` unchanged — **no new dependency**.
- Crypto (JWT HS256 + `X-Hub-Signature-256`) implemented with **stdlib only**
  (`hmac`, `hashlib`, `base64`, `secrets`, `datetime`).
- Constant-time comparisons use `hmac.compare_digest` throughout (no `==` on
  secrets/signatures).

## 12. Cross-cutting compliance

- **No PHI in envelopes/DTOs:** envelope carries only message-id, source phone,
  event type, timestamp.
- **No secrets committed:** webhook/JWT secrets in tests are string literals
  scoped to tests; no `.env`/credentials shipped.
- **No raw-body re-serialization:** signature verified over raw bytes before
  any parsing.

## 13. Exit criteria checklist

- [x] JWT signature validation present (stdlib, HS256, constant-time)
- [x] WhatsApp inbound verification (raw-body HMAC-SHA256 + verify-token handshake)
- [x] Neutral, PHI-minimal inbound envelope (no domain import in envelope)
- [x] No new dependency; `requirements.txt` unchanged
- [x] Additive-only boundary; legacy surface untouched
- [x] Single gate commit + gate tag
- [x] Full suite green (226 passed)
- [ ] Per-patient caregiver relationship authorization **(blocked — contract A)**
- [ ] Patient self-access via verified identity bridge **(blocked — contract B)**
- [ ] Webhook replay/idempotency store **(blocked — contract C)**

## 14. Commit / tag

- **Commit:** single commit on `feature/gate-06-api-security`
- **Tag (annotated):** `gate-06-api-security-complete`
- **STOP after this gate — Gate 07 is NOT started.** The three blocked
  checkboxes are the exact contracts to hand to the next responsible boundary.

## Afterword — STOP

Gate 06 is complete for its representable scope. The three NOT-IMPLEMENTED
items are reported with their exact missing contracts (A/B/C in §10) and are
**not** faked. No Gate 07 work is opened in this session.
