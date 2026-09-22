# WhatsApp Integration Security Specification

This document details the security model, cryptographic invariants, and zero-PHI guarantees governing the **THALI × P.L.A.T.E.** Meta WhatsApp Cloud API integration.

---

## 1. Threat Model & Mitigations

| Threat | Mitigation | Implementation |
|---|---|---|
| **Webhook Spoofing / Tampering** | Constant-time HMAC-SHA256 verification over raw bytes | `verify_x_hub_signature_256` in `signature.py` |
| **Replay Attacks** | Deduplication receipt store with 7-day retention | `SqlAlchemyWebhookReceiptStore` with unique `(provider, provider_message_id)` index |
| **Denial of Service (DoS)** | IP/phone rate limiting on webhook tier (120 req/min, burst 30) | `apply_rate_limit` in `rate_limit.py` |
| **Prompt Injection / Resource Drain** | Pre-domain Intent Firewall blocks arbitrary LLM queries | `IntentFirewall.evaluate` in `intent_firewall.py` |
| **PHI Leakage in Observability** | Zero PHI in logs, traces, exception messages, and metric labels | `WhatsAppChannelSender` and `_audit_for_worker` |
| **Cross-Tenant Data Leakage** | PostgreSQL Row-Level Security (RLS) + SECURITY DEFINER routing anchor | `public.resolve_channel_tenant` and scoped `UnitOfWork` |
| **Credential Exposure** | Strict environment variable separation; secrets never committed | `.env` gitignored, Pydantic settings loading |

---

## 2. Zero-PHI Guarantee

The application enforces a zero-PHI logging guarantee:

1. **Error Logging**:
   When Meta Cloud API returns an error (4xx/5xx), the sender logs:
   - HTTP status code
   - Meta error code (e.g. `190`, `130429`)
   - Meta error subcode
   - Meta `fbtrace_id`
   - Retryability flag
   **Never logged**: Recipient phone numbers, patient names, observation values, or message text.

2. **Metrics & Tracing**:
   Prometheus metrics (`whatsapp_deliveries_total`, `dependency_health_status`, `dependency_failures_total`) use only discrete outcome labels (`success`, `failure`) and normalized dependency identifiers (`whatsapp`).

3. **Audit Trail**:
   All audit records written to `audit_events` store only system actor IDs (`SYSTEM_WORKER`), resource UUIDs, and technical provenance metadata.

---

## 3. Webhook Signature Verification Invariant

The signature verification gate enforces:

```python
def verify_x_hub_signature_256(raw_body: bytes, signature_header: str | None, app_secret: str) -> None:
    # 1. Reject immediately if header missing or malformed prefix
    # 2. Compute expected HMAC-SHA256 over raw unparsed bytes
    # 3. Compare using hmac.compare_digest (constant time)
    # 4. If invalid, raise WebhookSignatureError (yielding HTTP 401)
```

No JSON deserialization, memory allocation for domain objects, or database operations occur before this function completes successfully.

---

## 4. Replay Deduplication Invariant

Every verified inbound delivery generates a unique `WebhookReceipt`:
- Primary key: `provider_message_id` (e.g. `wamid.HBgLMDExMQ==`)
- If the ID was already recorded within the 7-day retention window, `SqlAlchemyWebhookReceiptStore.record()` returns `fresh=False`.
- The webhook handler acknowledges duplicates with `HTTP 202 Accepted` and terminates immediately without enqueuing any background work.
- Receipt persistence and transactional outbox enqueue commit in **the same database transaction**:
  - A message is never acknowledged without its work item.
  - A duplicate delivery never creates duplicate domain state.

---

## 5. Intent Firewall Safety Barrier

To prevent arbitrary user input from driving automated workflows or leaking system prompts:
- The firewall classifies text using regex and linguistic taxonomies.
- Queries matching non-clinical patterns (poems, jokes, coding, weather, financial advice) are intercepted at the worker boundary.
- A standard, polite patient guidance message is returned.
- No LLM inferences, embeddings, or clinical commands are executed for unsupported messages.
