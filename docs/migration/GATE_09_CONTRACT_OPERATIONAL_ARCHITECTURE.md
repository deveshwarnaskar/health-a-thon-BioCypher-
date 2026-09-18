# GATE 09 — Contract & Operational Architecture
## THALI × P.L.A.T.E. Production Program

**Document ID**: `GATE-09-CONTRACT-OPERATIONAL-ARCHITECTURE`  
**Classification**: Architectural Analysis & Operational Contract Freeze (Read-Only Analysis)  
**Execution Date**: 2026-09-16  
**Current Working Branch**: `feature/gate-08-relational-identity`  
**Canonical Predecessors**:
- Gate 07: `fc3e594` (`gate-07-http-security-complete`)
- Gate 08 Implementation: `497774d` (`gate-08-relational-identity-complete`)
- Gate 08 Final Seal: `cf163ed` (`gate-08-relational-identity-sealed`)  
**Status**: ANALYSIS COMPLETE — IMPLEMENTATION LOCKED  
**Future Gate 10**: LOCKED (Awaiting Gate 09 Implementation Approval)  

---

## 1. Status

**ANALYSIS ONLY.**  
In accordance with program governance, this document defines the operational resiliency, idempotency, rate-limiting, audit immutability, and asynchronous channel orchestration architecture for Gate 09.
- **Source Code Changes**: 0
- **Test Changes**: 0
- **Database Migrations**: 0
- **Dependency Changes**: 0
- **Git Commits / Tags**: None
- **Gate 09 Implementation**: **NOT STARTED (LOCKED)**

---

## 2. Immutable Baseline

The repository is permanently anchored to the sealed Gate 08 checkpoint:
- Commit `cf163ed` (`gate-08-relational-identity-sealed`)
- Full test suite: **370 passed, 0 failed, 180 warnings**
- Zero breaking modifications to Gate 03 (Domain), Gate 04 (Application Ports), Gate 05 (Infrastructure & RLS), Gate 06 (Cryptographic Primitives), Gate 07 (HTTP Transport & Security), or Gate 08 (Relational Identity & Authorization).

---

## 3. Problem Statement

Gates 03 through 08 established an architecturally sound, type-safe, multi-tenant healthcare core with strict domain invariants, transaction-local PostgreSQL Row Level Security (RLS), cryptographic verification, and relationship-aware authorization.

However, real-world deployment of client applications (Universal Mobile in Gate 10, Admin Web in Gate 11) introduces distributed operational realities:
1. **Network Retries & Duplicates**: Mobile clients operating on spotty clinical WiFi or cellular networks retry `POST` requests when timeouts occur, risking duplicate glucose logs, duplicate meal observations, duplicate medication administration records, or duplicate care tasks.
2. **Provider Webhook Retries & Replays**: Meta WhatsApp Cloud API retries webhook deliveries aggressively if HTTP responses exceed 3 seconds, risking duplicate message processing, race conditions, or replay attacks.
3. **Denial-of-Service & Abuse**: Without rate limiting, authentication endpoints (`/api/v2/auth/*`) are vulnerable to brute-force attacks, expensive AI review endpoints (`/api/v2/clinical/ai-artifacts/*`) are vulnerable to financial denial-of-wallet, and webhooks are vulnerable to traffic flooding.
4. **Compliance & Audit Immutability**: While Gate 05 introduced structured privacy logging (`InfrastructureLogger`), clinical regulatory frameworks (HIPAA, DISHA, ISO 27001) require a durable, queryable, **immutable append-only audit trail** answering *who accessed or modified which clinical record, when, and with what outcome*, without logging Protected Health Information (PHI).
5. **Synchronous Webhook Bottlenecks**: Gate 07's WhatsApp webhook router parses envelopes synchronously during the HTTP request-response lifecycle. Processing clinical NLP or generative AI drafts synchronously within the HTTP thread causes timeout spikes, connection pool starvation, and webhook delivery failures.

Gate 09 wraps **operational resiliency, idempotency, and asynchronous channel orchestration** around the existing frozen security chain without bypassing any layer.

---

## 4. Scope

Gate 09 owns eight specific operational concerns:

A. **Idempotency**: Client-driven deduplication for state-changing HTTP requests via `Idempotency-Key`.  
B. **Replay Protection**: Channel-level defense verifying freshness and uniqueness of provider events.  
C. **Rate Limiting**: Sliding-window counter protecting auth, webhooks, and AI endpoints from abuse.  
D. **Immutable Audit Persistence**: Append-only, non-mutatable audit event store recording actor actions.  
E. **Channel Orchestration**: Provider-neutral messaging abstraction for outbound clinical notifications.  
F. **Asynchronous WhatsApp Processing**: Decoupled ingestion worker consuming verified outbox envelopes.  
G. **Retry-Safe Delivery Semantics**: Explicit at-least-once delivery combined with idempotent consumption.  
H. **Operational Failure Handling**: Rigorous fail-open vs. fail-closed matrices across Redis, DB, and network outages.  

---

## 5. Explicit Exclusions

The following areas are strictly **OUT OF SCOPE** for Gate 09 and must not be introduced:

- ❌ **Client Applications**: No React Native, Expo, Admin Web, P.L.A.T.E. Clinical Web, or UI/UX code.
- ❌ **Mobile Sync**: No offline SQLite, WatermelonDB, or client-side sync protocols (reserved for Gate 12).
- ❌ **Authorization Alterations**: Zero changes to Gate 07/08 RBAC, `CareTeamRole`, `CaregiverRelationship`, `IdentityPatientMapping`, or `RelationshipAuthorizationPolicy`.
- ❌ **Identity & Security Redesign**: Zero changes to Keycloak OIDC, PostgreSQL RLS, or JWT HS256 verifiers.
- ❌ **Clinical / AI Logic Expansion**: No automated diagnosis, clinical decision support, food recognition vision models, voice NLP, or automated prescription titration.
- ❌ **Enterprise Streaming Infrastructure**: No Apache Kafka, RabbitMQ, Celery, or distributed service meshes (e.g., Istio). PostgreSQL Outbox + `FOR UPDATE SKIP LOCKED` worker is the proven, minimal, self-contained architecture.

---

## 6. Existing Infrastructure Reuse

Gate 09 builds strictly upon assets delivered in previous gates:

| Component | Originating Gate | Existing Implementation | Gate 09 Reuse / Extension |
| :--- | :---: | :--- | :--- |
| **Relational Outbox** | Gate 05 | `DomainEventOutboxModel` (`domain_event_outbox` table) | Extend with worker leasing columns (`status`, `locked_at`, `retry_count`). |
| **Outbox Publisher** | Gate 05 | `SqlAlchemyOutboxDomainEventPublisher` | Reuse for atomic persistence of events alongside business transactions. |
| **Redis Client** | Gate 05 | `RedisCacheAdapter` (`backend/infrastructure/cache/`) | Reused for sliding-window rate limiting counters and fast idempotency locks. |
| **Privacy Redactor** | Gate 05 | `InfrastructureLogger` + `sanitize_log_dict` | Reused to sanitize audit metadata and prevent PHI/PII leakage into audit logs. |
| **Crypto Verifiers** | Gate 06 | `verify_x_hub_signature_256`, `verify_hs256` | Authoritative cryptographic gate executed *before* replay or rate checks. |
| **Webhook Envelope** | Gate 06 | `WhatsAppInboundEnvelope` | Neutral data transfer object passed from webhook router to outbox. |
| **Correlation Middleware** | Gate 07 | `CorrelationIDMiddleware` (`X-Correlation-ID`) | Authoritative correlation ID propagated into audit logs, outbox, and channel jobs. |
| **UnitOfWork & RLS** | Gate 05–08 | `SqlAlchemyUnitOfWork` with transaction-local RLS | Reused by background workers to enforce tenant isolation during async execution. |

---

## 7. Idempotency Contract

### 7.1 Conceptual Distinction: Idempotency vs. Deduplication vs. Replay Protection

To prevent architectural confusion, Gate 09 freezes the explicit distinction between these three operational concepts:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               OPERATIONAL SAFETY SPECTRUM                               │
├──────────────────────────┬──────────────────────────┬──────────────────────────────────┤
│        IDEMPOTENCY       │      DEDUPLICATION       │        REPLAY PROTECTION         │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Client-driven contract.  │ System-driven filter.    │ Security defense boundary.       │
│ Client provides unique   │ Transport drops duplicate│ Cryptographic verification of    │
│ header (Idempotency-Key) │ deliveries (e.g. Meta    │ freshness and single-use to stop │
│ to guarantee safe        │ webhook retry storms)    │ unauthorized re-transmission of  │
│ retries of API requests. │ before queue processing. │ captured legitimate payloads.    │
└──────────────────────────┴──────────────────────────┴──────────────────────────────────┘
```

### 7.2 IdempotencyStore Port Architecture

```python
class IdempotencyRecord:
    id: UUID
    tenant_id: UUID
    actor_id: UUID
    idempotency_key: str
    request_fingerprint: str  # SHA-256(method + path + body_bytes)
    status: IdempotencyStatus  # IN_PROGRESS | COMPLETED | FAILED
    status_code: int | None
    response_headers: dict[str, str] | None
    response_body: str | None
    created_at: datetime
    expires_at: datetime

class IdempotencyStore(Protocol):
    def reserve(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        key: str,
        fingerprint: str,
        ttl_seconds: int = 86400,
    ) -> ReservationResult: ...

    def complete(
        self,
        tenant_id: UUID,
        key: str,
        status_code: int,
        headers: dict[str, str],
        body: str,
    ) -> None: ...

    def release_failed(
        self,
        tenant_id: UUID,
        key: str,
    ) -> None: ...
```

### 7.3 Scoping & Composite Key Structure
An idempotency key provided by a client is never evaluated globally. It is strictly scoped to the tenant and actor:
$$\text{Storage Key} = \text{tenant\_id} \mathbin{\Vert} \text{actor\_id} \mathbin{\Vert} \text{Idempotency-Key}$$
*Security Invariant*: Actor A cannot hijack, collide with, or read the cached response of Actor B's idempotency key. Tenant A cannot collide with Tenant B.

### 7.4 Request Fingerprinting
The fingerprint is computed over canonical request metadata:
$$\text{fingerprint} = \text{HMAC-SHA256}\Big(\text{secret}, \text{HTTP\_METHOD} \mathbin{\Vert} \text{PATH} \mathbin{\Vert} \text{RAW\_BODY\_BYTES}\Big)$$

### 7.5 Idempotency Lifecycle & State Machine

```
               Client Request with Idempotency-Key
                                │
                                ▼
                   Check IdempotencyStore
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
   [ Key Not Found ]      [ IN_PROGRESS ]       [ COMPLETED ]
         │                      │                      │
   Reserve Key                  │                      ▼
  (IN_PROGRESS)                 │             Compare Fingerprints
         │                      │                      │
         ▼                      │             ┌────────┴────────┐
   Execute Handler              │             ▼                 ▼
         │                      │        [ Match ]        [ Mismatch ]
   ┌─────┴─────┐                │             │                 │
   ▼           ▼                ▼             ▼                 ▼
[ Success ] [ Failure ]    HTTP 409 Conflict  Return Cached     HTTP 409 Conflict
   │           │          (Concurrent Ingest) Response (200/201) (Key Reused with
   ▼           ▼                              + Replayed Header  Different Body)
Complete    Release
(COMPLETED) (Key Cleared)
```

1. **First Request**: Key is reserved with status `IN_PROGRESS`. Business use-case executes within the transaction. Upon commit, `complete()` writes the HTTP status code, safe response headers, and response body, marking status `COMPLETED`.
2. **Exact Retry (Same Key + Same Fingerprint)**: Returns the previously stored response immediately with HTTP header `Idempotent-Replayed: true`. No application handler or database transaction is re-executed.
3. **Payload Conflict (Same Key + Different Fingerprint)**: Returns `HTTP 409 Conflict` (`{"code": "IDEMPOTENCY_KEY_MISMATCH", "detail": "Idempotency key reused with different request payload"}`).
4. **Concurrent Duplicate (Same Key while `IN_PROGRESS`)**: Returns `HTTP 409 Conflict` (`{"code": "CONCURRENT_REQUEST_IN_PROGRESS", "detail": "A request with this idempotency key is currently processing"}`) or waits up to 2 seconds for completion before returning cached result.
5. **Failed Execution (Unhandled Error / Network Crash)**: If the use case raises an unexpected 500 error or database connection failure, `release_failed()` deletes the reservation or marks it `FAILED`. The key is **not permanently poisoned**, allowing the client to retry.
6. **Key Expiry**: Default TTL is 24 hours (86,400 seconds). After expiry, the key is purged and a subsequent request is treated as a new first request.

---

## 8. Webhook Replay & Deduplication Contract

### 8.1 Critical Ordering Invariant
> [!CRITICAL]
> **Cryptographic Verification MUST Precede Replay/Deduplication Checks.**
> Under no circumstances may an unverified webhook payload be checked against or inserted into deduplication storage. Deduplicating unverified payloads exposes the system to cache-poisoning Denial-of-Service attacks, where an attacker forges an envelope containing a victim's `message_id`, causing the authentic provider delivery to be rejected as a duplicate.

### 8.2 The Authoritative Webhook Inbound Pipeline

```
Meta WhatsApp Inbound HTTPS Delivery
  │
  ▼
[ 1. Raw-Body Signature Verification ] ───► FAIL: HTTP 401/403 (Gate 06 verify_x_hub_signature_256)
  │
  ▼ PASS
[ 2. JSON Structure Parsing ]          ───► FAIL: HTTP 400 Bad Request
  │
  ▼ PASS
[ 3. Provider ID & Timestamp Extract ]
  │  (Meta wamid.HBg... / statuses.id / fallback body hash)
  ▼
[ 4. Replay / Deduplication Check ]    ───► DUPLICATE: Return HTTP 200/202 (Acknowledge Meta, drop body)
  │  (Query webhook_receipts within 7-day retention window)
  ▼ FRESH
[ 5. Atomic Inbound Receipt Write ]
  │  (Insert into webhook_receipts + domain_event_outbox in same DB transaction)
  ▼
[ 6. Immediate Provider Ack ]
  │  (Return HTTP 202 Accepted within 500ms)
  ▼
[ 7. Asynchronous Intake Processing ]
     (Background worker polls outbox, executes application use-case)
```

### 8.3 Provider Identifier Resolution
1. **Primary Key**: Meta WhatsApp Message ID (`entry[0].changes[0].value.messages[0].id`, format `wamid.HBg...`).
2. **Status Update Key**: Meta Status ID (`entry[0].changes[0].value.statuses[0].id`).
3. **Fallback Deterministic Fingerprint**: If provider IDs are absent, compute `HMAC-SHA256(webhook_secret, raw_bytes)`.
4. **Retention Window**: 7 days (604,800 seconds). Duplicate deliveries within this window are acknowledged and dropped.

---

## 9. Rate Limiting Contract

### 9.1 RateLimiter Port Architecture

```python
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_epoch: int
    retry_after_seconds: int

class RateLimiter(Protocol):
    def check_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        burst_allowance: int = 0,
    ) -> RateLimitResult: ...
```

### 9.2 Rate Limiting Policy Matrix

| Tier / Endpoint Scope | Key Strategy | Default Limit | Burst | Failure Mode | Security Rationale |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Authentication** (`/api/v2/auth/*`) | `ip` + `tenant_id` | 10 req / min | 2 | **FAIL CLOSED** | Protects against credential stuffing and brute force. |
| **WhatsApp Webhook** (`/api/v2/webhooks/whatsapp`) | `channel_source_ip` | 100 req / sec | 20 | **FAIL OPEN** | Prevents dropped clinical readings during legitimate intake spikes. |
| **AI Review Operations** (`/api/v2/clinical/ai-artifacts/*`) | `actor_id` + `tenant_id` | 20 req / min | 5 | **FAIL CLOSED** | Prevents financial denial-of-wallet and LLM quota exhaustion. |
| **Clinical Observation Writes** (`/api/v2/clinical/observations`) | `actor_id` + `tenant_id` | 60 req / min | 10 | **FAIL OPEN / DEGRADE** | Preserves patient glucose and meal reporting availability. |
| **Administrative Operations** (`/api/v2/admin/*`) | `actor_id` + `tenant_id` | 30 req / min | 5 | **FAIL CLOSED** | Prevents rapid manipulation of identity mappings or facility records. |

### 9.3 Standard Response Headers
When rate limits are evaluated, the following HTTP headers are injected:
- `X-RateLimit-Limit`: Maximum allowed requests in window.
- `X-RateLimit-Remaining`: Remaining allowance in current window.
- `X-RateLimit-Reset`: Unix timestamp when quota resets.
- `Retry-After`: Seconds to wait before retrying (sent on `HTTP 429 Too Many Requests`).

### 9.4 Non-Negotiable Invariant
> Rate limiting is an **operational resilience mechanism**, not an authorization mechanism. Passing a rate limit check confers zero access rights. The request must still traverse RBAC, relationship verification, and PostgreSQL RLS.

---

## 10. AuditEvent Contract

### 10.1 Conceptual Audit Event Schema
The audit trail records security, compliance, and clinical access actions. It does not carry raw medical observation telemetry or sensitive secrets.

```python
@dataclass(frozen=True)
class AuditEvent:
    audit_event_id: UUID          # Primary Key (UUIDv7 or UUIDv4)
    tenant_id: UUID               # Multi-tenant scoping
    actor_id: UUID                # Keycloak sub claim or SYSTEM_WORKER UUID
    actor_type: str               # CLINICIAN | PATIENT | CAREGIVER | ADMIN | SYSTEM_WORKER
    action: str                   # READ | CREATE | UPDATE | REVOKE | REVIEW | LOGIN | DENIED
    resource_type: str            # PATIENT | GLUCOSE | MEAL | MEDICATION_PLAN | RELATIONSHIP | AI_ARTIFACT
    resource_id: str              # Identifier of the affected entity (stringified UUID)
    occurred_at: datetime         # UTC timestamp
    correlation_id: str           # Request correlation ID
    request_id: str               # HTTP / Webhook delivery request ID
    source_ip: str | None         # Client IP (truncated or masked)
    outcome: str                  # SUCCESS | DENIED | FAILED | CONFLICT
    reason: str | None            # Optional reason (e.g. "FACILITY_MISMATCH", "EXPIRED_RELATIONSHIP")
    provenance_metadata: dict     # Sanitized, non-PHI contextual metadata
```

### 10.2 Strict PHI & Secret Minimization Rules
The audit store must **never** record:
- Passwords, client secrets, API keys, verify tokens, webhook HMAC secrets.
- Bearer tokens, refresh tokens, or raw JWT strings.
- Clinical observation values (e.g., glucose reading `182.5 mg/dL`, meal description, food photo URL).
- Prescribed drug names or dosages (record `action="CREATE", resource_type="MEDICATION_PLAN", resource_id=UUID`).

---

## 11. Audit Immutability Guarantees

True audit immutability requires database-level enforcement, not mere application self-restraint.

### 11.1 Technical Enforcement Architecture
1. **Append-Only Database Permissions**:
   ```sql
   -- The application connection role 'thali_app_role' is strictly restricted
   GRANT INSERT, SELECT ON audit_events TO thali_app_role;
   REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM thali_app_role;
   ```
2. **Database Trigger Guard (Defense-in-Depth)**:
   ```sql
   CREATE OR REPLACE FUNCTION prevent_audit_mutation()
   RETURNS TRIGGER AS $$
   BEGIN
       RAISE EXCEPTION 'Audit records are immutable and cannot be updated or deleted.';
   END;
   $$ LANGUAGE plpgsql;

   CREATE TRIGGER trg_protect_audit_events
   BEFORE UPDATE OR DELETE ON audit_events
   FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();
   ```
3. **Application Port Invariant**: The `AuditStore` protocol provides only `record(event: AuditEvent) -> None` and `query(...) -> list[AuditEvent]`. There are no update or delete methods.

---

## 12. Domain Event vs. Audit Event vs. Channel Telemetry

Gate 09 strictly segregates these three event concepts:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              THREE-TIER EVENT TAXONOMY                                 │
├──────────────────────────┬──────────────────────────┬──────────────────────────────────┤
│       DOMAIN EVENT       │       AUDIT EVENT        │        CHANNEL TELEMETRY         │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Definition:              │ Definition:              │ Definition:                      │
│ Immutable fact within the│ Compliance record of an  │ Operational diagnostic metric    │
│ clinical bounded context.│ actor performing a security│ regarding network, transport, or│
│                          │ or clinical access action│ provider message delivery.       │
│ Examples:                │ Examples:                │ Examples:                        │
│ ObservationGlucoseLogged │ CLINICIAN_VIEWED_CHART   │ WhatsAppWebhookDelivered         │
│ MealPortionConfirmed     │ CAREGIVER_PROXY_LOGGED   │ OutboundMessageAckReceived       │
│ CareTaskCompleted        │ AUTHZ_FACILITY_MISMATCH  │ MetaCloudLatencyMs               │
│ Storage / Target:        │ Storage / Target:        │ Storage / Target:                │
│ domain_event_outbox table│ audit_events table       │ Prometheus / Logs / OpenTelemetry│
│ Rebuilds Domain State?   │ Rebuilds Domain State?   │ Rebuilds Domain State?           │
│ YES (Source of truth)    │ NO (Observer only)       │ NO (Ephemeral metrics)           │
└──────────────────────────┴──────────────────────────┴──────────────────────────────────┘
```

---

## 13. Transactional Outbox Pattern

### 13.1 Atomicity Guarantee
$$\text{Business Entity Mutation} + \text{Outbox Event Record} \in \text{Single Atomic Database Transaction}$$
If the database transaction commits, the event is guaranteed to be in the outbox. If the transaction rolls back, zero orphaned events exist.

### 13.2 Outbox Processing Lifecycle
Gate 09 extends the Gate 05 outbox table with leasing and retry mechanics:

```
      [ PENDING ] (Event written in same TX as clinical state)
           │
           │ Worker polls: SELECT ... FOR UPDATE SKIP LOCKED
           ▼
     [ PROCESSING ] (Leased with locked_at = NOW(), locked_by = worker_id)
           │
     ┌─────┴────────────────────────┐
     ▼                              ▼
[ Success ]                   [ Transient Error ]
     │                              │
Mark PUBLISHED                      │ retry_count < 5
(published_at = NOW())              ▼
                              Compute Exponential Backoff
                              (next_attempt_at = NOW() + 2^n * base)
                              Return to [ PENDING ]
                                    │
                                    │ retry_count >= 5
                                    ▼
                              [ DEAD_LETTER ]
                              (Alert operational engineers)
```

### 13.3 Worker Concurrency & Lock-Free Scaling
Multiple worker processes poll the outbox concurrently using PostgreSQL's native lock-skipping construct:
```sql
SELECT id, event_type, payload
FROM domain_event_outbox
WHERE status = 'PENDING'
  AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
ORDER BY occurred_at ASC
LIMIT 10
FOR UPDATE SKIP LOCKED;
```
This guarantees that worker instances never block each other, never process the same event simultaneously, and scale horizontally without distributed coordination locks.

---

## 14. Channel Orchestration

### 14.1 Provider-Neutral Outbound Port
Business logic must not couple to Meta WhatsApp Cloud API SDK semantics. Gate 09 defines an abstract messaging port:

```python
@dataclass(frozen=True)
class OutboundMessage:
    message_id: UUID
    tenant_id: UUID
    recipient_phone: str
    channel_type: str  # "WHATSAPP" | "SMS" | "PUSH"
    template_name: str
    template_params: dict[str, str]
    correlation_id: str

class DeliveryResult:
    success: bool
    provider_delivery_id: str | None
    error_code: str | None
    retryable: bool

class IChannelSender(Protocol):
    def send(self, message: OutboundMessage) -> DeliveryResult: ...
```

---

## 15. WhatsApp Asynchronous Intake Worker

### 15.1 Separation of Receiving from Processing
```
FastAPI Webhook Route (HTTP)
  └─► Validates signature
  └─► Checks dedup store
  └─► Inserts outbox event
  └─► Acknowledges Meta (202 Accepted)
          │ (Async boundary)
          ▼
Background Intake Worker (CLI / Service)
  └─► Leases outbox event
  └─► Establishes tenant context via UnitOfWork
  └─► Resolves sender phone to Patient in tenant
  └─► Dispatches IngestGlucoseReadingCommand or LogMealDraftCommand
  └─► Commits domain state + marks outbox event PUBLISHED
```

### 15.2 Invariant: No Bypass of Domain Boundaries
The intake worker is **not** a secondary business-logic engine. It extracts the raw text from the envelope, resolves the patient via `PatientRepository`, and dispatches the standard Gate 04 application command (`IngestGlucoseReadingCommand`). All domain invariants (20–600 mg/dL glucose range, meal confirmation status) are strictly executed.

---

## 16. Retry Semantics

### 16.1 At-Least-Once Delivery + Idempotent Consumption
Because true network "exactly-once" delivery is mathematically impossible in distributed systems, Gate 09 guarantees:
$$\text{Delivery: At-Least-Once} \quad + \quad \text{Consumption: Idempotent} \quad \equiv \quad \text{Effect: Exactly-Once}$$

### 16.2 Retry Backoff Schedule
- Attempt 1: Immediate
- Attempt 2: 2 seconds
- Attempt 3: 4 seconds
- Attempt 4: 8 seconds
- Attempt 5: 16 seconds
- Attempt 6: Transition to `DEAD_LETTER` with operational alert.

---

## 17. Operational Failure Matrix

| Component | Failure Condition | Impact | Operational Action / Mitigation |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | Connection timeout or pool exhaustion. | Writes and reads fail. | Fail closed. Return HTTP 503. Health probe `/health/ready` flips to unhealthy. |
| **Redis** | Redis crash or network partition. | Cache and rate limits affected. | Evaluate per-tier policy: Fail Closed on Auth; Fail Open on Webhooks; Degrade to DB on Idempotency. |
| **WhatsApp API** | Meta Cloud returns HTTP 5xx or times out. | Outbound notification delayed. | Outbox worker re-queues event with exponential backoff. Inbound unaffected. |
| **WhatsApp API** | Meta Cloud returns HTTP 4xx (e.g. invalid phone). | Notification impossible. | Non-retryable. Mark outbox entry `FAILED` with error code; emit audit event. |
| **Duplicate Webhook** | Meta re-delivers identical message. | Potential duplicate data. | Detected via `webhook_receipts`. Immediately return HTTP 200/202 and discard payload. |
| **Idempotency Conflict** | Client sends same key with altered payload. | Data ambiguity. | Return HTTP 409 Conflict. Preserve original record untouched. |
| **Worker Crash** | Worker process killed while executing job. | Outbox event in `PROCESSING`. | Lease expiry: after 5 minutes, event becomes eligible for re-lease by surviving workers. |
| **Audit Storage** | Audit insert fails (e.g. DB disk full). | Compliance breach risk. | If audit cannot be written for a state-changing write, transaction must roll back (fail closed). |

---

## 18. Redis Failure Policy

| Concern | Primary Storage | Redis Failure Policy | Justification |
| :--- | :--- | :---: | :--- |
| **Auth Rate Limiting** | Redis Sliding Window | **FAIL CLOSED (429)** | Defense against brute-force attacks takes priority during cache outage. |
| **Webhook Rate Limiting** | Redis Sliding Window | **FAIL OPEN** | Clinical data intake must not be lost due to cache infrastructure failure. |
| **General API Rate Limiting** | Redis Sliding Window | **DEGRADE (In-Memory)** | Falls back to local process in-memory counter with logged warning. |
| **Idempotency Records** | PostgreSQL Table | **DEGRADE (Direct DB)** | PostgreSQL is authoritative; Redis is only a fast cache. Zero consistency loss. |

---

## 19. Tenant Propagation for Background Workers

### 19.1 The Problem
Background workers operate outside the interactive HTTP request cycle and have no user JWT.

### 19.2 The Worker Tenant Binding Mechanism
1. **Outbox Events**: The outbox record contains an explicit, immutable `tenant_id` captured during the originating transactional write.
2. **Worker Context Initialization**:
   ```python
   # The worker establishes the exact same PostgreSQL RLS session context:
   uow = SqlAlchemyUnitOfWork(session_factory, tenant_id=job.tenant_id)
   # Under the hood, this executes:
   # set_config('app.current_tenant_id', :tid, true)
   ```
3. **Webhook Intake**: The channel router resolves the incoming phone number against `Patient` profiles within the specific organization's tenant scope (anchored by Meta WABA Phone Number ID mapping). Under no circumstances is an arbitrary `tenant_id` accepted from unverified message text.

---

## 20. Background Worker Security Boundary

- **Service Principal Identity**: Workers execute with an explicit internal actor identity (`actor_id = UUID("00000000-0000-0000-0000-000000000001")`, `actor_type = "SYSTEM_WORKER"`).
- **No Direct Table Mutations**: The worker is forbidden from executing raw SQL `UPDATE patients ...` or `INSERT INTO glucose_observations ...`.
- **Application Port Traversal**: All operations must execute via Gate 04 command handlers (`IngestGlucoseHandler`, `ConfirmMealObservationHandler`).
- **Audit Logging**: Every background operation executed by the worker generates an `AuditEvent` with `actor_type="SYSTEM_WORKER"`.

---

## 21. Correlation & Traceability

Three distinct identifiers provide end-to-end traceability without leaking PHI:

$$\text{Request ID} \quad \longrightarrow \quad \text{Correlation ID} \quad \longrightarrow \quad \text{Causation ID}$$

1. **`request_id`**: Scoped strictly to one HTTP transaction or webhook delivery.
2. **`correlation_id`**: Propagated through HTTP Header $\rightarrow$ Command $\rightarrow$ Domain Event $\rightarrow$ Outbox Row $\rightarrow$ Background Worker $\rightarrow$ Outbound WhatsApp Message $\rightarrow$ Audit Log.
3. **`causation_id`**: Points to the immediate parent event or message ID that directly triggered the current operation.

---

## 22. Observability & Operational Metrics

Gate 09 specifies standard Prometheus / OpenTelemetry metrics (zero PHI in metric labels):

- `thali_http_requests_total{method, endpoint, status_code}`
- `thali_idempotency_conflicts_total{tenant_id, endpoint}`
- `thali_webhook_replays_dropped_total{channel}`
- `thali_rate_limit_exceeded_total{scope}`
- `thali_outbox_queue_depth{status}`
- `thali_outbox_processing_duration_seconds{event_type}`
- `thali_outbox_dead_letter_total{event_type}`
- `thali_channel_delivery_success_total{channel}`
- `thali_channel_delivery_failure_total{channel, error_code}`

---

## 23. Security Threat Model

| Threat ID | Threat Vector | System Impact | Gate 09 Mitigation Control | Failure Mode |
| :--- | :--- | :--- | :--- | :--- |
| **T-09-01** | Replayed Webhook | Attacker re-sends valid signed WhatsApp webhook. | `webhook_receipts` table checks `provider_message_id`. Dropped as duplicate. | Ack HTTP 200, drop payload. |
| **T-09-02** | Webhook Dedup Cache Poisoning | Attacker sends unverified message with victim's `message_id`. | Signature verification strictly precedes deduplication check. | Reject HTTP 401 before dedup check. |
| **T-09-03** | Idempotency Key Hijacking | Actor A attempts to query or reuse Actor B's idempotency key. | Idempotency records strictly scoped to `(tenant_id, actor_id, key)`. | Key not found for Actor A; isolated. |
| **T-09-04** | Payload Tampering on Idempotent Retry | Client resends same key with altered dosage or patient ID. | Request fingerprint comparison (HMAC-SHA256). | HTTP 409 Conflict. |
| **T-09-05** | Rate Limit Brute Force via Distributed IPs | Attacker rotates IPs against single clinician account. | Composite rate-limiting key: `(tenant_id, actor_id)` for authenticated routes. | HTTP 429 Too Many Requests. |
| **T-09-06** | Outbox Poison Pill | Malformed payload causes worker to crash continuously. | Retry count tracked; moves to `DEAD_LETTER` after 5 attempts. | Isolate to dead letter; alert on-call. |
| **T-09-07** | Unauthorized Audit Record Deletion | Malicious insider attempts to erase audit trail. | Database permissions: `REVOKE UPDATE, DELETE ON audit_events FROM thali_app_role`. | PostgreSQL permission denied. |
| **T-09-08** | Cross-Tenant Worker Leakage | Worker processes Tenant A event under Tenant B RLS context. | Worker binds `tenant_id` from immutable outbox record to UoW session RLS. | RLS blocks cross-tenant access. |

---

## 24. API Impact Matrix

| Route | Idempotency-Key Required? | Rate Limited? | Audit Event Recorded? | Replay Protection? | Outbox / Async? |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `POST /api/v2/auth/verify` | No | **YES (Auth Tier)** | **YES (LOGIN)** | No | No |
| `GET /api/v2/clinical/observations` | No | **YES (Read Tier)** | **YES (CHART_READ)**| No | No |
| `POST /api/v2/clinical/observations` | **YES (Optional/Rec)**| **YES (Write Tier)**| **YES (OBS_CREATE)** | No | Yes (Outbox) |
| `POST /api/v2/clinical/medication-plans`| **YES (Recommended)** | **YES (Write Tier)**| **YES (PLAN_CREATE)**| No | Yes (Outbox) |
| `POST /api/v2/clinical/ai-artifacts/{id}/review` | **YES** | **YES (AI Tier)** | **YES (AI_REVIEW)** | No | Yes (Outbox) |
| `POST /api/v2/patients/{id}/caregivers` | **YES** | **YES (Write Tier)**| **YES (REL_CREATE)** | No | Yes (Outbox) |
| `POST /api/v2/admin/identity/mappings` | **YES** | **YES (Admin Tier)**| **YES (MAP_CREATE)** | No | Yes (Outbox) |
| `POST /api/v2/webhooks/whatsapp` | No (Uses Meta ID)| **YES (Webhook Tier)**| **YES (WH_RECEIPT)** | **YES (7-day Dedup)** | **YES (Outbox Intake)** |

---

## 25. Mobile Client Impact (Preparation for Gate 10)

Gate 10 (Universal Mobile Application) will rely on these concrete Gate 09 guarantees:
1. **Safe Retries via `Idempotency-Key`**: The mobile app generates a UUIDv4 `Idempotency-Key` header for every meal, glucose, or task submission. In case of network dropouts, the app retries safely without creating duplicate patient readings.
2. **Transparent Replay Response**: When retrying, the client receives the cached 200/201 response with header `Idempotent-Replayed: true`.
3. **Structured Error Codes**: Standardized HTTP 409 (`IDEMPOTENCY_KEY_MISMATCH`) and HTTP 429 (`RATE_LIMITED` with `Retry-After`) allow Expo client to handle offline queues gracefully.
4. **Correlation Tracing**: Mobile app can provide `X-Correlation-ID` to track customer support tickets end-to-end.

---

## 26. Admin / Web Impact (Preparation for Gate 11)

Admin Web Console and Clinical Workstations will consume:
1. **Audit Trail Views**: Filtered, tenant-isolated audit logs (`GET /api/v2/admin/audit-events`).
2. **Outbox & Channel Health**: Visibility into dead-letter queues and message delivery statuses.
3. **Administrative Operation Safety**: Identity mapping modifications protected against duplicate clicks via idempotency.

---

## 27. Test Architecture (Specification Only)

Gate 09 implementation will require the following test suites:

### 27.1 Unit Tests
- `test_idempotency_store_reservation_lifecycle`
- `test_idempotency_fingerprint_mismatch_returns_conflict`
- `test_rate_limiter_sliding_window_counter`
- `test_audit_event_phi_sanitization`
- `test_outbox_exponential_backoff_calculation`

### 27.2 Integration Tests
- `test_postgresql_audit_events_immutability_revokes_update_delete`
- `test_postgresql_outbox_skip_locked_concurrent_workers`
- `test_redis_rate_limiter_expiry_and_fallback`
- `test_webhook_receipts_deduplication_under_concurrency`

### 27.3 Security Tests
- `test_idempotency_key_cross_tenant_isolation_blocked`
- `test_idempotency_key_cross_actor_isolation_blocked`
- `test_unverified_webhook_cannot_poison_dedup_cache`
- `test_worker_tenant_context_enforces_rls_boundaries`

### 27.4 Failure & Chaos Tests
- `test_redis_down_auth_fails_closed`
- `test_redis_down_webhook_fails_open`
- `test_redis_down_idempotency_degrades_to_postgres`
- `test_worker_crash_releases_lease_after_timeout`

---

## 28. Proposed Persistence Model (Alembic Schema)

### 28.1 `idempotency_records` Table
```sql
CREATE TABLE idempotency_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    request_fingerprint VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'IN_PROGRESS',
    status_code INT NULL,
    response_headers JSONB NULL,
    response_body TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL
);

ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_idempotency ON idempotency_records
FOR ALL
USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE UNIQUE INDEX uq_idempotency_tenant_actor_key
ON idempotency_records(tenant_id, actor_id, idempotency_key);

CREATE INDEX ix_idempotency_expiry ON idempotency_records(expires_at);
```

### 28.2 `webhook_receipts` Table
```sql
CREATE TABLE webhook_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(32) NOT NULL,
    provider_message_id VARCHAR(256) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    processed_at TIMESTAMPTZ NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'RECEIVED'
);

CREATE UNIQUE INDEX uq_webhook_provider_message
ON webhook_receipts(provider, provider_message_id);

CREATE INDEX ix_webhook_receipts_received ON webhook_receipts(received_at);
```

### 28.3 `audit_events` Table
```sql
CREATE TABLE audit_events (
    audit_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL,
    actor_type VARCHAR(32) NOT NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    correlation_id VARCHAR(64) NOT NULL,
    request_id VARCHAR(64) NOT NULL,
    source_ip VARCHAR(64) NULL,
    outcome VARCHAR(20) NOT NULL,
    reason VARCHAR(256) NULL,
    provenance_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_audit_events ON audit_events
FOR ALL
USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE INDEX ix_audit_tenant_occurred ON audit_events(tenant_id, occurred_at);
CREATE INDEX ix_audit_actor ON audit_events(tenant_id, actor_id);
CREATE INDEX ix_audit_resource ON audit_events(tenant_id, resource_type, resource_id);
```

### 28.4 `domain_event_outbox` Table Extension
```sql
ALTER TABLE domain_event_outbox
ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
ADD COLUMN retry_count INT NOT NULL DEFAULT 0,
ADD COLUMN next_attempt_at TIMESTAMPTZ NULL,
ADD COLUMN locked_at TIMESTAMPTZ NULL,
ADD COLUMN locked_by VARCHAR(64) NULL,
ADD COLUMN last_error TEXT NULL;

CREATE INDEX ix_outbox_lease
ON domain_event_outbox(status, next_attempt_at)
WHERE status IN ('PENDING', 'PROCESSING');
```

---

## 29. Gate 09 Implementation Sequence

When implementation authorization is granted, Gate 09 will proceed in four strictly verified phases:

1. **Phase 1: Persistence & Core Ports**
   - Implement Alembic migration for `idempotency_records`, `webhook_receipts`, `audit_events`, and `domain_event_outbox` leasing columns.
   - Implement `SqlAlchemyIdempotencyStore` and `SqlAlchemyAuditStore`.
   - Implement database permission revocation on `audit_events`.
2. **Phase 2: HTTP Operational Middleware & Interceptors**
   - Implement `IdempotencyMiddleware` / endpoint dependency.
   - Implement `RateLimitMiddleware` using Redis adapter with fail-open/fail-closed policies.
   - Implement `AuditLoggingMiddleware` capturing request context.
3. **Phase 3: Webhook Deduplication & Outbox Worker**
   - Update `POST /api/v2/webhooks/whatsapp` to enforce `webhook_receipts` deduplication post-signature-check.
   - Implement background outbox polling worker using `FOR UPDATE SKIP LOCKED`.
   - Connect inbound envelope worker to application command handlers.
4. **Phase 4: Full Verification & Load Testing**
   - Execute unit, integration, concurrency, security, and failure test suites.
   - Verify 100% pass across all 370 existing tests + new Gate 09 tests.

---

## 30. Exit Criteria

Gate 09 will be complete when all of the following conditions are verified green:
- [ ] `IdempotencyStore` operational, enforcing composite `(tenant, actor, key)` isolation.
- [ ] WhatsApp webhook deduplicates deliveries post-signature verification.
- [ ] Rate limiter enforces tier policies and respects fail-open/fail-closed rules.
- [ ] `audit_events` table enforces PostgreSQL-level immutability (no `UPDATE`/`DELETE`).
- [ ] Background worker processes outbox concurrently via `SKIP LOCKED` without race conditions.
- [ ] Worker binds tenant context to PostgreSQL RLS before invoking application commands.
- [ ] All 370 existing Gate 00–08 tests continue to pass 100% without modification.

---

## 31. Known Unknowns & Technical Risks

1. **Meta WhatsApp Outbound Delivery Latency**: Meta Cloud API response times vary by geography. Outbound delivery worker must enforce a strict 5-second socket timeout to avoid tying up worker pool threads.
2. **Database Connection Pool Exhaustion under Worker Spikes**: Running multiple worker processes on the same PostgreSQL database requires connection pool budgeting (allocating separate pools for HTTP API vs. Outbox workers).
3. **Audit Event Log Growth**: High-throughput installations generate millions of audit records. Partitioning `audit_events` by month via PostgreSQL declarative partitioning or TimescaleDB must be scheduled before multi-hospital production rollouts.

---

## 32. Gate 10 Handoff Contract

Upon completion of Gate 09, the backend API provides the following **immutable service guarantees** to client applications:

1. **Mobile Application (Gate 10 — Universal React Native + Expo)**:
   - May safely retry any `POST` request with `Idempotency-Key: <UUID>`.
   - Guaranteed that network timeouts will never duplicate glucose entries, meals, or medication administrations.
   - Receives clean `HTTP 429` with `Retry-After` header when rate limits are approached.
2. **Admin Web Console (Gate 11)**:
   - Queryable compliance audit trail (`/api/v2/admin/audit-events`).
   - Outbox queue observability.
3. **Clinical Workstations (Gate 13)**:
   - Real-time WhatsApp intake updates processed reliably in the background without UI latency spikes.

---
*Document sealed on 2026-09-16. Gate 09 Architecture & Contract Analysis complete. Implementation locked.*
