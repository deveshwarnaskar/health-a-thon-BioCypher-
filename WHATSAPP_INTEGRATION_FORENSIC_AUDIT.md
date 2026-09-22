# THALI × P.L.A.T.E. Connected Diabetes-Care System
## Forensic Technical Discovery & Production Readiness Audit: WhatsApp Integration

**Audit Date**: September 21, 2026  
**Auditor**: Senior Staff Clinical Systems Architecture & Security Auditor  
**Scope**: Read-Only Forensic Codebase Discovery of WhatsApp Channel Integration  
**Target Repository**: `health-a-thon-BioCypher--master`  
**Current Branch**: `feature/authentication-lifecycle`  
**Working Tree Status**: Read-only discovery. Zero code modifications, zero migrations, zero commits, zero pushes.

---

## 1. Executive Summary

This forensic discovery audit evaluates the existing WhatsApp integration within the **THALI × P.L.A.T.E.** healthcare system. The evaluation traces every component, schema, route, parser, outbox event, and external integration boundary to answer the primary architectural question:

> *"What is the current state of WhatsApp integration in this application?"*

### Primary Findings
1. **Integration Status**: WhatsApp integration **DOES EXIST** in the backend codebase as an asynchronous event-driven subsystem. It is **NOT** a mere documentation stub or mock.
2. **Current Maturity Level**: **LEVEL 2 — BACKEND PROTOTYPE**.
   - The inbound webhook pipeline (Meta handshake, raw HMAC-SHA256 signature verification, receipt deduplication, transactional outbox enqueuing) is cleanly implemented and adheres to production security standards.
   - The outbound sender (`WhatsAppChannelSender`) formats and dispatches HTTP requests to Meta's Cloud API (`graph.facebook.com/v21.0/{phone_number_id}/messages`) for text and simple templates.
   - Inbound text messages in English and Hinglish are parsed deterministically (using regex and nutrition taxonomy) into canonical glucose readings (`IngestGlucoseReading`) and meal drafts (`LogMealDraft` with a conversational confirmation loop).
3. **Critical Architectural Gaps & Blockers**:
   - **Identity Model**: Account phone numbers are blindly trusted as WhatsApp identities (`patients.phone == source_phone`). There is **no verified WhatsApp linking mechanism**, no OTP verification, and no `whatsapp_identities` table.
   - **Caregiver Channel Access**: Caregiver-originated WhatsApp messages are **completely unsupported**. Inbound routing only queries `patients.phone`; caregiver accounts, caregiver delegations, and proxy authorizations are bypassed or dropped.
   - **Media Handling**: Inbound WhatsApp images, voice notes, audio files, and documents are **100% unhandled and dropped**. Only `text.body` is extracted from webhooks.
   - **Operational Deployment**: The outbox worker (`backend/interfaces/cli/worker.py`) is a standalone CLI script that must be manually invoked. It is **not** managed by a production process supervisor (systemd/supervisord/celery/docker-compose).
   - **Live Meta Verification**: All automated tests rely on mock HMAC signatures and simulated responses; the system has **never been validated against a real Meta Cloud API sandbox or production WABA in automated testing**.

---

## 2. Current WhatsApp Architecture

The WhatsApp channel operates as an asynchronous, decoupled edge ingestion channel:

```
[Meta WhatsApp Cloud API]
          │
          │ HTTPS POST (Signed with X-Hub-Signature-256)
          ▼
[FastAPI Webhook: /api/v2/webhooks/whatsapp]
  1. verify_x_hub_signature_256(raw_body, secret)  --> 401 if invalid
  2. _parse_delivery(raw_body)                     --> Extracts message_id, phone, text
  3. SqlAlchemyWebhookReceiptStore.record()        --> Deduplicates on (provider, msg_id)
  4. SqlAlchemyOutboxDomainEventPublisher.publish() --> Writes "whatsapp.message.received"
  5. Return 202 Accepted to Meta
          │
          ▼ Transactional Database Commit (Atomic)
[PostgreSQL: webhook_receipts + domain_event_outbox]
          │
          │ Leased by background polling loop
          ▼
[OutboxWorker (CLI: backend.interfaces.cli.worker)]
          │
          ├──> [SqlAlchemyChannelTenantResolver]
          │      Executes public.resolve_channel_tenant(phone)
          │      Queries: SELECT tenant_id, id FROM patients WHERE phone = :phone
          │
          ├──> [Hinglish Parser / Intake Transform]
          │      parse_intake_text(text)
          │      ├── Glucose regex --> IngestGlucoseReading --> IngestGlucoseHandler
          │      └── Food taxonomy --> LogMealDraft --> LogMealDraftHandler
          │
          ├──> [Meal Confirm/Correct Loop]
          │      If text is "YES"/"Haan"/"Small"/"Medium"
          │      Calls ConfirmMealObservationHandler
          │
          ├──> [Outbound Reply Dispatch]
          │      WhatsAppChannelSender.send()
          │      POST https://graph.facebook.com/v21.0/{phone_number_id}/messages
          │
          └──> [Immutable Audit Log]
                 SqlAlchemyAuditStore.record(AuditEvent)
```

---

## 3. Repository Components

The WhatsApp-related components are organized across the clean architecture layers of `backend/`:

- **HTTP Interfaces (`backend/interfaces/http/v2/webhooks/`)**:
  - `router.py`: Handshake (`GET`) and payload intake (`POST`) endpoints.
  - `whatsapp/signature.py`: Raw body HMAC-SHA256 verification.
  - `whatsapp/verify_token.py`: Meta challenge/verify token handshake.
  - `whatsapp/envelope.py`: Neutral inbound data representation.
- **Outbox Worker & Operations (`backend/application/ops/`, `backend/interfaces/cli/`)**:
  - `worker.py`: Background worker CLI process for leasing and executing outbox jobs.
  - `handlers.py`: `WhatsAppIntakeHandler`, `ChannelDeliveryHandler`.
  - `contracts.py`: Operational data shapes (`WebhookReceipt`, `OutboxJob`, `OutboundMessage`).
  - `intake_text.py`: Message dispatching and command generation.
- **Domain & Domain Events (`backend/domain/`)**:
  - `events/channel.py`: `WhatsAppMessageReceived`, `ChannelMessageQueued`.
  - `entities/notification.py`: `Notification`, `NotificationChannel.WHATSAPP`, `FORBIDDEN_NOTIFICATION_FIELDS`.
- **Infrastructure & Adapters (`backend/infrastructure/`)**:
  - `channel/whatsapp_sender.py`: Meta Graph API HTTP sender (`urllib.request`).
  - `parsing/hinglish_parser.py`: Indian English & Hinglish text parser.
  - `parsing/nutrition_taxonomy.py`: Regional food classification and nutrition estimator.
  - `persistence/ops/tenant_resolver.py`: Phone-to-patient tenant lookup.
  - `persistence/models/ops_models.py`: `WebhookReceiptModel`, `AuditEventModel`.
  - `persistence/models/notification_models.py`: `NotificationModel`.
- **Configuration (`config/`)**:
  - `settings.py`: `WhatsAppConfig` (`verify_token`, `app_secret`, `access_token`, `phone_number_id`, `api_version`).

---

## 4. WhatsApp Code Inventory

| Component | File | Symbol/Function/Class | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Webhook Verify** | `backend/interfaces/http/v2/webhooks/router.py` | `whatsapp_verify()` | **IMPLEMENTED** | Validates `hub.verify_token` via constant-time compare; echoes `hub.challenge`. |
| **Signature Verifier** | `backend/interfaces/http/v2/webhooks/whatsapp/signature.py` | `verify_x_hub_signature_256()` | **IMPLEMENTED** | Computes HMAC-SHA256 over raw request bytes; uses `hmac.compare_digest`. |
| **Verify Token Helper** | `backend/interfaces/http/v2/webhooks/whatsapp/verify_token.py` | `challenge_response()` | **IMPLEMENTED** | Strict check on `hub.mode == "subscribe"`. |
| **Webhook Intake Route** | `backend/interfaces/http/v2/webhooks/router.py` | `whatsapp_webhook()` | **IMPLEMENTED** | Verifies signature, dedups receipt, publishes outbox event in 1 transaction; returns 202. |
| **Payload Parser** | `backend/interfaces/http/v2/webhooks/router.py` | `_parse_delivery()` | **PARTIALLY_IMPLEMENTED** | Parses `messages[0].text.body`; ignores images, audio, documents, interactive buttons. |
| **Receipt Deduplication** | `backend/infrastructure/persistence/ops/replay_store.py` | `SqlAlchemyWebhookReceiptStore` | **IMPLEMENTED** | PostgreSQL uniqueness on `(provider, provider_message_id)` with 7-day retention. |
| **Outbox Event Publisher**| `backend/infrastructure/persistence/uow/outbox_publisher.py` | `SqlAlchemyOutboxDomainEventPublisher` | **IMPLEMENTED** | Atomic write of `whatsapp.message.received` into `domain_event_outbox`. |
| **Outbox Worker** | `backend/interfaces/cli/worker.py` | `OutboxWorker`, `build_worker()` | **PARTIALLY_IMPLEMENTED** | Polling loop leases outbox jobs. Runs only as CLI script; no background daemon config. |
| **Inbound Intake Handler**| `backend/application/ops/handlers.py` | `WhatsAppIntakeHandler.handle()` | **PARTIALLY_IMPLEMENTED** | Resolves patient, detects ambiguity, runs confirm loop, dispatches glucose/meal commands. |
| **Tenant/Patient Resolver**| `backend/infrastructure/persistence/ops/tenant_resolver.py` | `SqlAlchemyChannelTenantResolver` | **SCAFFOLDED** | Direct lookup `patients.phone == phone`. No separate WhatsApp identity verification. |
| **Routing SQL Function** | `backend/infrastructure/persistence/alembic/versions/0003_operational_resiliency.py` | `public.resolve_channel_tenant()` | **SCAFFOLDED** | `SECURITY DEFINER` function querying `patients` table by phone number only. |
| **Hinglish Parser** | `backend/infrastructure/parsing/hinglish_parser.py` | `parse_inbound()`, `_reading_from_text()` | **IMPLEMENTED** | Regex and keyword matching for glucose readings, meal descriptions, confirmations. |
| **Nutrition Taxonomy** | `backend/infrastructure/parsing/nutrition_taxonomy.py` | `classify_text()`, `estimate_nutrition()` | **IMPLEMENTED** | Local dictionary lookup for common Indian foods; calculates carbs and GI category. |
| **Glucose Dispatcher** | `backend/application/ops/intake_text.py` | `parse_intake_text()` | **IMPLEMENTED** | Converts text to `IngestGlucoseReading(value, taken_at, tag)`. |
| **Meal Dispatcher** | `backend/application/ops/intake_text.py` | `parse_intake_text()` | **IMPLEMENTED** | Converts text to `LogMealDraft(description, portion, carbs_grams)`. |
| **Meal Confirm Loop** | `backend/application/ops/handlers.py` | `WhatsAppIntakeHandler.handle()` (Step 2) | **IMPLEMENTED** | Identifies pending meals, accepts "YES"/"Haan"/portion updates, calls `ConfirmMealObservation`. |
| **Outbound Sender** | `backend/infrastructure/channel/whatsapp_sender.py` | `WhatsAppChannelSender.send()` | **PARTIALLY_IMPLEMENTED** | Dispatches HTTP POST to Meta Graph API. Only supports text and simple template messages. |
| **Outbound Job Handler**| `backend/application/ops/handlers.py` | `ChannelDeliveryHandler.handle()` | **IMPLEMENTED** | Executes `sender.send()`, records delivery audit, updates notification status. |
| **Notification Service**| `backend/application/services/notification_service.py` | `NotificationService.send_notification()`| **IMPLEMENTED** | Persists `Notification`, publishes `channel.message.queued`, enforces PHI restrictions. |
| **Caregiver Resolver** | None | None | **MISSING** | Inbound intake does not check `caregiver_relationships` or caregiver permissions. |
| **WhatsApp Identity Linking**| None | None | **MISSING** | No table, API, or flow exists to link or verify a WhatsApp phone number. |
| **Media Downloader** | None | None | **MISSING** | No code downloads media from `graph.facebook.com/v21.0/{media_id}`. |
| **Audio Transcription**| None | None | **MISSING** | No speech-to-text or voice note transcription integration exists. |
| **Food Image AI** | None | None | **MISSING** | No vision model or food image recognition pipeline connected to WhatsApp. |
| **Template Management**| None | None | **MISSING** | Templates are hardcoded strings; no WABA template synchronization or registration. |

---

## 5. Current Inbound Message Flow

Tracing an incoming WhatsApp message through the exact codebase:

```
[1. Meta WhatsApp Cloud API]
      │ Sends POST to /api/v2/webhooks/whatsapp with header X-Hub-Signature-256: sha256=<HMAC>
      ▼
[2. backend/interfaces/http/v2/webhooks/router.py: whatsapp_webhook()]
      │ Calls verify_x_hub_signature_256(raw_body, signature_header, app_secret)
      │ [REAL: cryptographic verification over raw body bytes]
      ▼
[3. backend/interfaces/http/v2/webhooks/router.py: _parse_delivery()]
      │ Extracts provider_message_id, source_phone, event_type, text
      │ [SCAFFOLDED: only extracts messages[0].text.body; ignores all non-text payloads]
      ▼
[4. backend/infrastructure/persistence/ops/replay_store.py: record()]
      │ Writes to table `webhook_receipts`. If duplicate, fresh=False
      │ [REAL: PostgreSQL unique constraint uq_webhook_receipt_provider_msg]
      ▼
[5. backend/infrastructure/persistence/uow/outbox_publisher.py: publish()]
      │ If fresh, writes WhatsAppMessageReceived to `domain_event_outbox`
      │ [REAL: atomic transactional outbox pattern]
      ▼
[6. Router returns HTTP 202 Accepted to Meta]
      │ Fast ACK (<50ms). Downstream processing is completely asynchronous.
      ▼
[7. backend/interfaces/cli/worker.py: OutboxWorker.process_once()]
      │ Worker leases row from `domain_event_outbox` with status='processing'
      │ [REAL but REQUIRES MANUAL PROCESS: No background daemon configured]
      ▼
[8. backend/application/ops/handlers.py: WhatsAppIntakeHandler.handle()]
      │ Calls self._tenant_resolver.resolve(phone)
      │ [SCAFFOLDED: SqlAlchemyChannelTenantResolver calls public.resolve_channel_tenant()]
      │ [SECURITY GAP: Directly queries patients WHERE phone = :phone. Blind trust of phone number.]
      ▼
[9. Resolve Patient & Context]
      │ If phone not found: raises PermanentWorkerFailure (dropped, no user reply)
      │ If patient deactivated: raises DomainError (dropped, failure audit logged)
      │ [MISSING: Caregiver resolution is 100% absent]
      ▼
[10. Intent Classification & Parsing]
      │ ambiguous_reading_values(text) --> If ambiguous, replies with clarification prompt
      │ parse_inbound(text) --> If "YES"/"Haan"/portion, executes ConfirmMealObservationHandler
      │ parse_intake_text(text) --> Deterministic parsing:
      │   - Glucose: IngestGlucoseReading
      │   - Meal: LogMealDraft (with nutrition lookup)
      │ [REAL: 100% deterministic regex and dictionary parsing; no LLM used]
      ▼
[11. Command Execution & Canonical Persistence]
      │ Glucose: IngestGlucoseHandler writes GlucoseObservation to PostgreSQL `observations`
      │ Meal: LogMealDraftHandler writes MealObservation to PostgreSQL `meals`
      │ [REAL: Writes directly to canonical clinical tables]
      ▼
[12. Outbound WhatsApp Confirmation / Prompt]
      │ WhatsAppIntakeHandler._send_reply() calls WhatsAppChannelSender.send()
      │ [REAL Meta API format: POST graph.facebook.com/v21.0/{phone_id}/messages]
      ▼
[13. Audit Trail]
      │ SqlAlchemyAuditStore records AuditEvent in `audit_events` with provenance={"channel": "whatsapp"}
      │ [REAL: PHI-minimal audit logging]
```

---

## 6. Current Outbound Flow

Tracing outbound WhatsApp messages (notifications, reminders, confirmation prompts):

```
[Application Trigger: NotificationService / ReminderScheduler / WhatsAppIntakeHandler]
      │
      ▼
[backend/application/services/notification_service.py: send_notification()]
  1. Validates patient is active.
  2. If recipient != patient, validates caregiver relationship in `caregiver_relationships`.
  3. Enforces information asymmetry: rejects forbidden fields (carbs_grams, glycemic_index,
     clinical_notes, ai_review, ai_diagnosis, risk_score) in template parameters.
  4. Inserts row into `notifications` table (status='queued').
  5. Publishes `ChannelMessageQueued` domain event to `domain_event_outbox`.
  6. Writes `NOTIFICATION_DISPATCHED` to `audit_events`.
  7. Commits UoW transaction atomically.
      │
      ▼
[Worker Loop: backend/interfaces/cli/worker.py]
      │ Leases `channel.message.send` event from `domain_event_outbox`.
      ▼
[backend/application/ops/handlers.py: ChannelDeliveryHandler.handle()]
      │ Maps event payload to OutboundMessage value object.
      │ Calls self._sender.send(message).
      ▼
[backend/infrastructure/channel/whatsapp_sender.py: WhatsAppChannelSender.send()]
  1. Checks credentials: if access_token or phone_number_id unset, returns CREDENTIALS_MISSING.
  2. Builds JSON payload:
     - If template: {"messaging_product": "whatsapp", "to": phone, "type": "template", "template": ...}
     - If text: {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": ...}}
  3. Dispatches HTTP POST to https://graph.facebook.com/v21.0/{phone_number_id}/messages.
  4. Translates response:
     - 2xx: DeliveryResult(success=True, provider_delivery_id=messages[0].id)
     - 4xx: DeliveryResult(success=False, retryable=False) -> permanent failure
     - 5xx/timeout: DeliveryResult(success=False, retryable=True) -> exponential backoff retry
      ▼
[Status Reconciliation]
  If SUCCESS: notification.mark_delivered(delivered_at=now)
  If RETRYABLE: notification.requeue_for_retry() (up to 5 retries via outbox)
  If PERMANENT: notification.mark_failed(reason)
  Writes delivery outcome to `audit_events`.
```

---

## 7. Webhook Forensic Audit

### GET Handshake Endpoint (`GET /api/v2/webhooks/whatsapp`)
- **Route Definition**: [`backend/interfaces/http/v2/webhooks/router.py:68-83`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/interfaces/http/v2/webhooks/router.py#L68-L83).
- **Parameters Evaluated**: `hub.mode`, `hub.verify_token`, `hub.challenge`.
- **Token Verification**: Handled by `confirm_verify_token()` in [`verify_token.py:17-21`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/interfaces/http/v2/webhooks/whatsapp/verify_token.py#L17-L21). Uses `hmac.compare_digest(query_token, configured_token)` for constant-time comparison against timing attacks.
- **Fail-Closed Verification**: If `hub.mode != "subscribe"` or token fails to match, raises `HTTPException(403, detail="Verification failed")`.
- **Challenge Echo**: Returns `{"challenge": hub_challenge}` as required by Meta's webhook verification protocol.
- **Evaluation**: **PRODUCTION-CAPABLE**.

### POST Inbound Receiver (`POST /api/v2/webhooks/whatsapp`)
- **Route Definition**: [`backend/interfaces/http/v2/webhooks/router.py:138-205`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/interfaces/http/v2/webhooks/router.py#L138-L205).
- **Raw Body Handling**: Reads `raw_body = await request.body()` **before** JSON parsing.
- **Signature Verification**: Verifies `X-Hub-Signature-256` header over the exact raw byte stream using `app_secret` via `verify_x_hub_signature_256()` ([`signature.py:24-47`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/interfaces/http/v2/webhooks/whatsapp/signature.py#L24-L47)). Rejects missing, malformed, or mismatched signatures with `HTTPException(401)`.
- **Payload Parsing**: Extracts `messages[0]` or `statuses[0]`. If `messages[0].id` is missing, generates deterministic HMAC fallback ID `build_fingerprint()`.
- **Rate Limiting**: Applies sliding-window webhook rate limit (`apply_rate_limit`) scoped by source phone or message ID.
- **Deduplication & Atomicity**: In a single SQLAlchemy transaction:
  1. Inserts into `webhook_receipts`. If `(provider, provider_message_id)` already exists, `fresh = False`.
  2. If `fresh and event_type == "message_received"`: enqueues `WhatsAppMessageReceived` to `domain_event_outbox`.
  3. If duplicate: does not enqueue work, commits receipt check, and returns 202.
  4. If database fails: rolls back and returns HTTP 503 so Meta will retry delivery.
- **Evaluation**: **PRODUCTION-CAPABLE ARCHITECTURE**.
- **Limitation**: `_parse_delivery` only extracts `messages[0].text.body`. Multi-message webhooks (arrays of $>1$ message) and non-text messages are truncated.

---

## 8. Meta WhatsApp Cloud API Audit

- **Client File**: [`backend/infrastructure/channel/whatsapp_sender.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/infrastructure/channel/whatsapp_sender.py).
- **Graph API Base URL**: `https://graph.facebook.com` (configurable).
- **API Version**: Defaults to `v21.0` (configurable via `THALI_WHATSAPP__API_VERSION`).
- **Endpoint Invoked**: `POST https://graph.facebook.com/{version}/{phone_number_id}/messages`.
- **Authentication**: `Authorization: Bearer {access_token}` header.
- **HTTP Transport**: Python standard library `urllib.request` (no third-party SDK dependencies).
- **Payload Support**:
  - `text`: Sends `{"type": "text", "text": {"body": message}}`.
  - `template`: Sends `{"type": "template", "template": {"name": template_name, "language": {"code": "en"}, "components": [{"type": "body", "parameters": [...]}]}}`.
- **Missing Meta API Capabilities**:
  1. **Media Upload & Download**: No calls to `POST /{phone_number_id}/media` or `GET /{media_id}`.
  2. **Interactive Messages**: No support for interactive buttons (`quick_reply`, `call_to_action`), list messages, or flow messages.
  3. **WABA Management**: No WABA ID lookup, business profile query, or template approval status polling.
  4. **Language Localization**: Language is hardcoded to `{"code": "en"}`; Hindi/Hinglish template language codes (`hi`, `hi_IN`) are not parameterized.
  5. **Token Lifecycle**: No token refresh/exchange logic; assumes a long-lived Meta System User Access Token is injected as an environment variable.

---

## 9. WhatsApp Identity Model

### Forensic Finding: SEVERE ARCHITECTURAL GAP
The existing codebase **DOES NOT DISTINGUISH** between an **Account Phone Number** and a **Verified WhatsApp Connected Identity**.

#### Code Evidence:
1. In [`backend/application/ops/handlers.py:151`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/application/ops/handlers.py#L151):
   ```python
   resolved = self._tenant_resolver.resolve(phone.strip())
   ```
2. In [`backend/infrastructure/persistence/ops/tenant_resolver.py:61-65`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/infrastructure/persistence/ops/tenant_resolver.py#L61-L65):
   ```python
   stmt = (
       select(PatientModel.id, PatientModel.tenant_id)
       .where(PatientModel.phone == normalized, PatientModel.active.is_(True))
       .limit(1)
   )
   ```
3. In [`backend/infrastructure/persistence/alembic/versions/0003_operational_resiliency.py:185-190`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/infrastructure/persistence/alembic/versions/0003_operational_resiliency.py#L185-L190):
   ```sql
   SELECT p.tenant_id, p.id
   FROM patients p
   WHERE p.phone = resolve_channel_tenant.phone
     AND p.active
   ORDER BY p.created_at
   LIMIT 1;
   ```

#### Implications:
- **No Dedicated Identity Entity**: There is no `whatsapp_identities` table, no `whatsapp_id` (wa_id) column, and no verification timestamp.
- **Blind Trust Vulnerability**: If Alice signs up on the mobile app and enters phone number `+919876543210` without completing an SMS OTP verification, anyone possessing that WhatsApp number can immediately send messages that are committed directly into Alice's medical record.
- **No Multi-Tenant Phone Isolation**: `LIMIT 1` in `resolve_channel_tenant` orders by `created_at`. If two tenants inadvertently register the same phone number, messages are routed arbitrarily to the older tenant.

---

## 10. Patient WhatsApp Connection Flow

### Forensic Finding: MISSING
The real-world lifecycle (`NOT_CONNECTED` $\rightarrow$ `CONNECT_REQUESTED` $\rightarrow$ `VERIFICATION_PENDING` $\rightarrow$ `VERIFIED` $\rightarrow$ `ACTIVE` $\rightarrow$ `REVOKED`) **does not exist**.

| Lifecycle Stage | Implementation Status | Evidence |
| :--- | :--- | :--- |
| **Connection Request** | **MISSING** | No mobile UI, no backend API endpoint for requesting WhatsApp connection. |
| **Verification Token / OTP** | **MISSING** | No SMS or WhatsApp OTP verification flow exists. |
| **Verified State** | **MISSING** | No database column tracks whether a phone number is verified on WhatsApp. |
| **Unlink / Revoke** | **MISSING** | No mechanism for a patient to unlink their WhatsApp number. |
| **Identity Reconnection** | **MISSING** | If a patient changes numbers, only an administrative SQL update can update `patients.phone`. |

---

## 11. Caregiver WhatsApp Authorization

### Forensic Finding: MISSING / UNROUTED
The system cannot process caregiver-originated WhatsApp messages.

#### Walkthrough Scenario:
A verified caregiver sends: *"Mom's glucose is 142"* from their personal phone `+919111111111`.
1. Inbound webhook receives message from `+919111111111`.
2. `WhatsAppIntakeHandler` calls `SqlAlchemyChannelTenantResolver.resolve("+919111111111")`.
3. The resolver executes:
   `SELECT tenant_id, id FROM patients WHERE phone = '+919111111111' AND active = true`.
4. **Outcome A**: If the caregiver is NOT registered as a patient, `resolve()` returns `None`. `WhatsAppIntakeHandler` raises:
   `PermanentWorkerFailure("sender phone resolves to no patient in any tenant")`.
   The message is permanently dead-lettered without user notification.
5. **Outcome B**: If the caregiver IS also registered as a patient in the same clinic, the resolver resolves the caregiver's own `patient_id`. The reading $142\text{ mg/dL}$ is committed to the **caregiver's** personal chart, rather than Mom's chart.
6. The `caregiver_relationships` table is **completely ignored** during inbound intake.

---

## 12. Unknown Number Handling

When an unknown WhatsApp number sends a message (e.g. *"Sugar 140"*):
1. Webhook verifies signature and commits delivery receipt to `webhook_receipts`.
2. Enqueues `WhatsAppMessageReceived` to `domain_event_outbox`.
3. Worker leases the job and invokes `WhatsAppIntakeHandler`.
4. `self._tenant_resolver.resolve(phone)` returns `None`.
5. Handler executes [`handlers.py:152-154`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/application/ops/handlers.py#L152-L154):
   ```python
   if resolved is None:
       # Unknown sender → cannot route safely → permanent, no retries.
       raise PermanentWorkerFailure("sender phone resolves to no patient in any tenant")
   ```
6. **Safety Evaluation**:
   - **Safe Against Clinical Corruption**: No patient record is touched, and no clinical data is created.
   - **Safe Against Data Leakage**: No reply is sent, ensuring zero PHI is leaked to the unknown number.
   - **Operational Defect**: The unknown user receives complete radio silence (no message indicating *"Your number is not registered with THALI"*). No unlinked contact record is retained for support triage.

---

## 13. Inbound WhatsApp Message Type Support

| Message Type | Webhook Accepted | Parsed | Persisted | Canonical Event Created | Current Implementation Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TEXT** | **YES** | **YES** | Outbox JSON & Canonical tables | `GlucoseObservation`, `MealObservation` | **IMPLEMENTED** (Hinglish/English text) |
| **IMAGE** | YES (HTTP 202) | **NO** (`text=""`) | Ignored | None | **MISSING** (Media payload dropped) |
| **AUDIO / VOICE** | YES (HTTP 202) | **NO** (`text=""`) | Ignored | None | **MISSING** (Voice payload dropped) |
| **DOCUMENT** | YES (HTTP 202) | **NO** (`text=""`) | Ignored | None | **MISSING** (PDF/attachment dropped) |
| **LOCATION** | YES (HTTP 202) | **NO** (`text=""`) | Ignored | None | **MISSING** |
| **INTERACTIVE (Button)**| YES (HTTP 202) | **NO** | Ignored | None | **MISSING** (Button replies dropped) |
| **LIST_REPLY** | YES (HTTP 202) | **NO** | Ignored | None | **MISSING** |
| **CONTACT** | YES (HTTP 202) | **NO** | Ignored | None | **MISSING** |
| **REACTION** | YES (HTTP 202) | **NO** | Ignored | None | **MISSING** |

---

## 14. Glucose Message Flow

- **Supported Syntax**:
  - Bare numbers: `"142"`, `"180"` (mapped to postprandial by default).
  - Tag + Number: `"fasting 110"`, `"before meal: 95"`, `"khali pet 105"`.
  - Number + Tag: `"140 fasting"`, `"180 after dinner"`.
  - Conversational sentences: `"aaj subah sugar 135 tha"`, `"glucose reading is 142 mg/dl"`.
- **Parsing Engine**: [`backend/infrastructure/parsing/hinglish_parser.py:185-230`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/infrastructure/parsing/hinglish_parser.py#L185-L230).
- **Physical Boundary Validation**: Values $<20\text{ mg/dL}$ or $>600\text{ mg/dL}$ are rejected as `InvalidGlucoseValue` (domain error).
- **Ambiguity Detection**: Queries like `"sugar 140 ya 240"` or `"shayad 180"` trigger `ambiguous_reading_values()`, sending a WhatsApp clarification request without logging an unconfirmed reading.
- **Confirmation State**: Ingested with `confirmation = PatientConfirmationState.PENDING`. Glucose readings do not undergo a confirmation loop.
- **Timestamp Fidelity**:
  - **Defect**: The parser does **not** extract time-of-day (e.g. *"at 8 AM"*). `taken_at` is set to `self._clock.now()` (the time the worker processed the job), overwriting the true occurrence time.

---

## 15. Food & Meal WhatsApp Flow

- **Supported Syntax**: Hinglish food items (e.g. `"2 roti dal sabzi"`, `"rice rajma"`, `"had biryani"`, `"chhota bowl dal"`).
- **Parsing Engine**:
  1. `hinglish_parser.py` extracts portion letters (`s`, `m`, `l`) and cleans common transliterations (`ruti` $\rightarrow$ `roti`, `daaal` $\rightarrow$ `dal`).
  2. `nutrition_taxonomy.py:classify_text()` identifies food items from regional taxonomy.
  3. `nutrition_taxonomy.py:estimate_nutrition()` estimates `carbs_grams` and `gi_category`.
- **Confirmation Workflow**:
  1. System creates unconfirmed draft: `LogMealDraft(description, portion, carbs_grams, is_ambiguous=False)`.
  2. In `LogMealDraftHandler`, persists `MealObservation` with `confirmation = PENDING`.
  3. Sends WhatsApp reply: *"Aapne '2 roti dal' khaya? Kripya confirm karein (YES/Haan ya portion: Small / Medium / Large)."*
  4. Patient replies: `"YES"`, `"Haan"`, or `"Large"`.
  5. Intake handler receives confirmation $\rightarrow$ executes `ConfirmMealObservationHandler`.
  6. Entity state moves to `CONFIRMED` (or `CORRECTED`).
  7. Sends WhatsApp confirmation: *"Dhanyawad! Aapka meal record ho gaya hai."*
- **Information Asymmetry Verification**:
  - **PASSED**. Neither `carbs_grams` nor `glycemic_index` is exposed in the WhatsApp message reply sent to the patient.

---

## 16. Timestamp Model Audit

| Timestamp Semantic | Architectural Meaning | Existing WhatsApp Implementation | Status |
| :--- | :--- | :--- | :--- |
| `occurred_at` | When the reading or meal occurred in physical reality | Set to `self._clock.now()` when worker processes message. Text-specified time (e.g. "at 8 AM") is ignored. | **PARTIAL** |
| `captured_at` | When user provided input to WhatsApp | Meta webhook timestamp is ignored in `_parse_delivery`. | **MISSING** |
| `received_at` | When backend received HTTP webhook | Recorded in `webhook_receipts.received_at`. | **IMPLEMENTED** |
| `synced_at` | When record committed to canonical DB | Recorded in `observations.created_at`. | **IMPLEMENTED** |

---

## 17. Confirmation Model Audit

- **Meal Observations**: Fully implemented conversational draft-then-confirm state machine (`PENDING` $\rightarrow$ `CONFIRMED` / `CORRECTED`).
- **Glucose Observations**: Ingested directly into `observations` with `confirmation = PENDING`. No conversational confirmation prompt is dispatched.
- **Safety Violation**: None. Unconfirmed meal drafts are explicitly flagged as `pending` and are not promoted to clinical evidence until confirmed.

---

## 18. Canonical Event Model Integration

- **Entities Created**: Standard `GlucoseObservation` and `MealObservation` domain entities.
- **Database Tables**: Inserted directly into canonical PostgreSQL tables `observations` and `meals`.
- **Provenance Gap**:
  - Neither `GlucoseObservation` nor `MealObservation` entities possess a `source_type` or `channel` column.
  - Channel provenance is recorded **only** in the `audit_events` table (`provenance_metadata={"channel": "whatsapp", "provider_message_id": "..."}`).
  - Consequently, once stored, database queries cannot differentiate whether an observation came from the mobile app or WhatsApp without performing an expensive join against audit logs.

---

## 19. Timeline & P.L.A.T.E. Integration

- **THALI Mobile Timeline**:
  - Queries `GET /api/v2/clinical/patients/{id}/observations`.
  - Because WhatsApp records are written directly to PostgreSQL `observations` and `meals`, they are **immediately visible** in the mobile timeline.
  - **Limitation**: The UI cannot display a "WhatsApp" badge because the observation DTO lacks source attribution.
- **Doctor P.L.A.T.E.**:
  - Queries `GET /api/v2/clinical/patients/{id}/clinical-observations`.
  - WhatsApp-originated records participate immediately in deterministic clinical calculations (TIR, TAR, TBR, GMI, CV).

---

## 20. AI Integration in WhatsApp Pipeline

- **LLM Usage**: Zero LLMs or generative AI models are invoked during WhatsApp intake.
- **Parsing Mechanism**: 100% deterministic regex rules, phonetic replacement dictionaries (`_TYPO_MAP`), and standard Indian nutrition taxonomies.
- **Clinical Safety Compliance**:
  - **PASSED**. AI does not diagnose, prescribe, titrate medications, or make autonomous clinical decisions over WhatsApp.

---

## 21. Evidence Pipeline Integration

- Ingested observations generate domain events (`GlucoseObservationRecorded`, `MealObservationConfirmed`).
- The backend `EvidenceBuilder` aggregates these canonical observations into `AIReviewArtifact` objects for doctor review.
- Provenance reference to the original WhatsApp `message_id` is preserved in `audit_events`, but is lost in the observation record itself.

---

## 22. Media Handling Audit

### Forensic Finding: COMPLETELY ABSENT
- When an image (e.g. food photo) or voice note is sent via WhatsApp:
  1. Meta's webhook sends an event containing `{"type": "image", "image": {"id": "12345", "mime_type": "image/jpeg"}}`.
  2. In [`router.py:124`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/backend/interfaces/http/v2/webhooks/router.py#L124), `_parse_delivery` accesses `(message.get("text") or {}).get("body", "")`, which returns `""`.
  3. The outbox receives `text=""`, which is rejected by `hinglish_parser.py` as `kind="refusal"`.
  4. No download request is made to Meta's Graph API (`GET /{media_id}`).
  5. No integration with MinIO/S3 object storage exists for WhatsApp media.

---

## 23. Voice / Audio Handling Audit

### Forensic Finding: COMPLETELY ABSENT
- WhatsApp voice notes (`type="audio"`) are ignored at the webhook boundary.
- There is no speech-to-text integration (Whisper / Google Cloud Speech-to-Text).

---

## 24. Security Audit

| Security Domain | Existing Implementation | Vulnerability / Gap | Severity |
| :--- | :--- | :--- | :--- |
| **Webhook Signature** | Constant-time HMAC-SHA256 over raw body bytes before parsing | None. Compliant with Meta security requirements. | **SAFE** |
| **Verify Token** | Constant-time string comparison in GET challenge handshake | None. | **SAFE** |
| **Phone Authentication** | Direct lookup on `patients.phone` | **Account phone is blindly trusted. Attacker can spoof readings if victim's phone is unverified.** | **CRITICAL** |
| **Multi-Tenancy** | `resolve_channel_tenant` uses `LIMIT 1` ordered by creation date | Cross-tenant collision if two tenants have identical phone numbers. | **HIGH** |
| **Replay / Duplicate** | Unique constraint on `(provider, provider_message_id)` in `webhook_receipts` | None. Replayed webhooks receive 202 without duplicate execution. | **SAFE** |
| **Rate Limiting** | In-memory / Redis token bucket sliding window per phone number | None. Protects webhook receiver from denial of service. | **SAFE** |
| **Information Leakage** | `FORBIDDEN_NOTIFICATION_FIELDS` filters clinical metrics from outbound messages | None. Clean patient/caregiver information asymmetry. | **SAFE** |

---

## 25. Privacy & PHI Exposure Audit

- **Raw Request Body**: Raw webhook JSON bodies are **not stored** in the database or written to log files.
- **Message Content**: Extracted message text is persisted transiently in `domain_event_outbox.payload` until processed by the worker.
- **Audit Trails**: `audit_events` strictly excludes message text, clinical values, and patient identifiers in accordance with Gate 09 §10 specifications.
- **Log Sanitation**: Structured logs omit phone numbers and message content.

---

## 26. Idempotency & Retries Audit

- **Webhook Deduplication**: Enforced via `WebhookReceiptModel` with unique constraint `uq_webhook_receipt_provider_msg`.
- **Outbox Worker Retries**:
  - Transient errors (HTTP 5xx, timeouts): Exponential backoff ($2^{n-1}$ seconds) up to 5 retries.
  - Permanent errors (HTTP 4xx, unknown phone, domain rejection): Marked as permanent failure (`DeliveryOutcome.PERMANENT`), no retries.
- **Replay Safety**: Safe. Meta webhook retries with identical `message_id` return HTTP 202 without creating duplicate database rows.

---

## 27. Failure Modes & Behavioral Matrix

| Failure Mode | Current System Behavior | Safe Behavior? | Missing Production Behavior |
| :--- | :--- | :--- | :--- |
| **Invalid Signature** | Returns HTTP 401 Unauthorized immediately | **YES** | None. |
| **Duplicate Webhook** | Acknowledges with HTTP 202; drops outbox enqueue | **YES** | None. |
| **Unknown Phone Number** | Drops job; marks outbox row failed | **PARTIAL** | Should send polite rejection message: *"Number not registered with THALI"*. |
| **Deactivated Patient** | DomainError raised; failure logged in audit | **YES** | Should notify sender that account is inactive. |
| **Caregiver Message** | Fails to resolve patient; permanently dropped | **NO** | Must resolve caregiver relationship, capability, and target patient. |
| **Ambiguous Reading** | Replies via WhatsApp asking for single clear reading | **YES** | None. |
| **Invalid Glucose (e.g. 999)**| DomainError raised; permanently dropped | **YES** | Should reply: *"Reading out of physiologically valid range (20-600 mg/dL)"*. |
| **Meta API 5xx / Timeout**| Worker retries with exponential backoff | **YES** | None. |
| **Meta API 4xx (Bad Token)**| Marked permanent failure; alerts logged | **YES** | Requires alerting / credentials rotation hook. |
| **Inbound Media Sent** | Silently dropped; text is empty | **NO** | Should reply: *"Image/Voice logging via WhatsApp is not currently supported"*. |

---

## 28. Environment & Deployment Configuration

### Existing Variables in `config/settings.py` & `.env.example`:
- `THALI_WHATSAPP__VERIFY_TOKEN`: Token for GET handshake.
- `THALI_WHATSAPP__APP_SECRET`: App secret for HMAC-SHA256 verification.
- `THALI_WHATSAPP__ACCESS_TOKEN`: System User token for Cloud API.
- `THALI_WHATSAPP__PHONE_NUMBER_ID`: Meta phone number ID.
- `THALI_WHATSAPP__API_VERSION`: Graph API version (`v21.0`).

### Missing Environment Variables:
- `THALI_WHATSAPP__WABA_ID`: WhatsApp Business Account ID (required for template management).
- `THALI_WHATSAPP__WEBHOOK_URL`: Public webhook callback URL for automated health verification.

### Deployment Blocker:
- In [`deploy/production/docker-compose.production.yml`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/deploy/production/docker-compose.production.yml), there is **no container service configured to run the outbox worker** (`backend.interfaces.cli.worker --poll`). Inbound webhooks will be enqueued into the database, but **will never be processed** unless someone manually runs the worker CLI.

---

## 29. Test Coverage Analysis

### Existing WhatsApp Tests:
- `tests/api/test_whatsapp_webhook.py`: 12 tests covering verify-token handshake, valid HMAC signatures, tampered signatures, and rate limiting.
- `tests/api/test_whatsapp_webhook_replay.py`: Tests duplicate webhook delivery and idempotency.
- `tests/unit/ops/test_whatsapp_confirm_loop.py`: Tests Hinglish parsing, meal draft generation, and confirmation loop with in-memory fakes.
- `tests/api/test_gate_10l_notifications_whatsapp.py`: 28 tests for outbound notifications, RLS isolation, and forbidden field enforcement.
- `tests/security/test_whatsapp_webhook.py`: Security tests for signature timing attacks and payload tampering.

### Testing Limitations:
- **100% Mocked**: Zero tests connect to Meta's Cloud API sandbox or live servers.
- **No Inbound Media Tests**: Zero tests for images, voice notes, or documents.
- **No Identity Linking Tests**: Zero tests for linking or unlinking WhatsApp numbers.

---

## 30. Production Deployability Assessment

> **Question**: *"If we created a real Meta WhatsApp Business account today and supplied valid credentials, could this repository receive and send WhatsApp messages in production without substantial new implementation?"*

### Answer: **NO**

### Reasons:
1. **Worker Process Not Containerized**: No background worker container exists in `docker-compose.production.yml` to process `domain_event_outbox`. Webhooks would be accepted with 202, but would sit unprocessed forever.
2. **Account Takeover Vulnerability**: The system trusts unverified account phone numbers. Any user could register a doctor or patient's phone number and log readings on their behalf.
3. **Caregiver Inbound Is Broken**: Caregivers cannot log telemetry for dependents.
4. **Media Is Dropped**: Users sending meal photos or voice notes receive complete radio silence.
5. **Unknown Numbers Receive Radio Silence**: Unregistered users receive no guidance or onboarding message.

---

## 31. Architecture Gap Matrix

| Capability | Current State | Evidence in Repository | Required for Production | Architectural Gap |
| :--- | :--- | :--- | :--- | :--- |
| **1. Meta Cloud API Client** | PARTIAL | `backend/infrastructure/channel/whatsapp_sender.py` | Full Graph API client | Missing media, interactive, and template APIs |
| **2. WABA Configuration** | MISSING | `config/settings.py` lacks WABA ID | WABA account binding | No WABA ID setting or template sync |
| **3. Webhook Handshake** | IMPLEMENTED | `backend/interfaces/http/v2/webhooks/router.py` | Public Meta GET challenge | None (Production ready) |
| **4. Signature Verification** | IMPLEMENTED | `backend/interfaces/http/v2/webhooks/whatsapp/signature.py` | HMAC-SHA256 verification | None (Production ready) |
| **5. Delivery Deduplication** | IMPLEMENTED | `backend/infrastructure/persistence/ops/replay_store.py` | Idempotent webhook receipt store | None (Production ready) |
| **6. WhatsApp Identity Model** | MISSING | `backend/infrastructure/persistence/ops/tenant_resolver.py` | `whatsapp_identities` table | Phone number is blindly trusted |
| **7. Number Verification Flow** | MISSING | None | SMS / WhatsApp OTP verification | No linking or verification workflow |
| **8. Caregiver Routing** | MISSING | None | Relationship + capability lookup | Caregiver inbound messages dropped |
| **9. Unknown Number Handling** | PARTIAL | `backend/application/ops/handlers.py` | Polite rejection / Onboarding | User receives radio silence |
| **10. Glucose Extraction** | IMPLEMENTED | `backend/infrastructure/parsing/hinglish_parser.py` | Ingest valid glucose readings | Time-of-day parsing missing |
| **11. Meal Confirmation Loop** | IMPLEMENTED | `backend/application/ops/handlers.py` | Draft $\rightarrow$ confirmation loop | None (Production ready for text) |
| **12. Media (Photo) Ingestion** | MISSING | None | Meta media download + S3 store | Images completely dropped |
| **13. Voice Note Ingestion** | MISSING | None | Audio download + Whisper transcription | Voice notes completely dropped |
| **14. Canonical Provenance** | PARTIAL | `backend/domain/entities/` | Record channel on observation | Channel only in audit logs, not entity |
| **15. Worker Supervisor** | MISSING | `deploy/production/docker-compose.production.yml` | Containerized background daemon | Outbox worker exists only as manual CLI |

---

## 32. Recommended Implementation Phases

```
PHASE W1: Foundation & Identity Model
  - Create `whatsapp_identities` table (tenant_id, user_id, wa_id, phone, status, verified_at).
  - Implement 6-digit OTP verification flow via WhatsApp template message.
  - Implement account linking and unlinking APIs.

PHASE W2: Worker Daemon & Deployment Containerization
  - Add `worker` service to `deploy/production/docker-compose.production.yml`.
  - Add systemd / supervisor configuration for `backend.interfaces.cli.worker --poll`.
  - Implement health checks and dead-letter queue monitoring for outbox.

PHASE W3: Caregiver Delegation Routing
  - Update `SqlAlchemyChannelTenantResolver` to resolve:
    wa_id -> Caregiver User -> Active Caregiver Relationship -> Target Patient.
  - Handle dependent selection context if caregiver monitors multiple patients.

PHASE W4: Unknown Number & Conversational Onboarding
  - Send polite canned guidance when an unknown number contacts the bot.
  - Provide a one-time link to download the THALI mobile app or initiate account linking.

PHASE W5: Media & Food Photo Ingestion
  - Parse `messages[0].image` in `_parse_delivery`.
  - Call Meta Graph API `GET /{media_id}` to retrieve download URL.
  - Stream image to private S3/MinIO bucket.
  - Connect to AI food recognition draft generator.

PHASE W6: Voice Note & Audio Telemetry
  - Parse `messages[0].audio` in `_parse_delivery`.
  - Retrieve audio file from Meta; store in S3.
  - Transcribe voice via Whisper / Google STT.
  - Pass transcript to Hinglish parser for glucose/meal extraction.

PHASE W7: Live Sandbox & Meta Business Verification
  - Set up Meta Developer Sandbox credentials in staging.
  - Execute end-to-end automated live test harness.
  - Register Meta-approved notification templates.
```

---

## 33. Open Questions

1. **Meta Business Account (WABA)**: Has a verified Meta Business Account and verified phone number been provisioned for THALI?
2. **Dependent Resolution for Caregivers**: If a caregiver cares for two elderly diabetic parents, how should WhatsApp determine which parent a message refers to? (e.g. interactive button picker or keyword prefix like *"Mom: sugar 140"*).
3. **Session Expiry on Confirmations**: If a patient logs a meal draft via WhatsApp at 1:00 PM and replies *"YES"* at 9:00 PM, what is the maximum validity window before the pending draft expires?

---

## 34. Final Verdict

### Current WhatsApp Maturity Level:
$$\mathbf{LEVEL\ 2\ —\ BACKEND\ PROTOTYPE}$$

- **WHAT EXISTS TODAY**:
  - Secure Meta webhook verify handshake (`GET`) and raw body HMAC-SHA256 signature verification (`POST`).
  - Webhook delivery receipt deduplication with 7-day replay window.
  - Atomic transactional outbox publishing (`whatsapp.message.received`).
  - Deterministic Hinglish/English text parser for glucose readings and food descriptions.
  - Meal draft conversational confirmation loop over WhatsApp.
  - Outbound WhatsApp Cloud API sender (`POST graph.facebook.com/v21.0/{phone_id}/messages`).
  - PHI-restricted notification service with strict field filtering.
- **WHAT DOES NOT EXIST**:
  - Verified WhatsApp identity linking (account phone is blindly trusted).
  - Caregiver WhatsApp inbound delegation routing.
  - Inbound media handling (photos, voice notes, documents).
  - Background worker container in production deployment.
  - Live Meta sandbox integration in CI.
- **WHAT IS MOCKED**:
  - All automated tests mock the Meta Graph API.
  - Test suites use hardcoded mock HMAC secrets.
- **WHAT IS PRODUCTION-CAPABLE**:
  - Webhook cryptographic signature verification.
  - Webhook receipt deduplication.
  - Outbox transactional reliability.
  - Outbound notification PHI safeguards.
- **WHAT BLOCKS REAL META CONNECTION**:
  - Containerization of the outbox worker process.
  - Verification of Meta System User Token and Phone Number ID in live staging.
- **WHAT BLOCKS REAL PATIENT USE**:
  - Absence of an explicit WhatsApp phone verification flow.
  - Inability to handle food photos or voice notes.
- **WHAT BLOCKS REAL CAREGIVER USE**:
  - Absence of caregiver-to-patient relationship lookup during inbound intake.
- **WHAT MUST BE BUILT NEXT**:
  - Dedicated `whatsapp_identities` table and verification workflow.
  - Worker service entry in `docker-compose.production.yml`.

---

## 35. Executive Summary Table & Plain-Language Answers

### Executive Summary Table

| Area | Status | Production Ready? |
| :--- | :--- | :--- |
| **Meta API** | PARTIALLY_IMPLEMENTED | **NO** (Text/basic templates only; no media/interactive APIs) |
| **Webhook** | IMPLEMENTED | **YES** (Standard Meta contract implemented) |
| **Signature** | IMPLEMENTED | **YES** (Constant-time HMAC-SHA256 over raw body) |
| **Idempotency** | IMPLEMENTED | **YES** (Provider message ID deduplication ledger) |
| **Identity** | SCAFFOLDED | **NO** (Blind trust of account phone number) |
| **Patient Linking** | MISSING | **NO** (No verification or linking workflow) |
| **Caregiver Linking** | MISSING | **NO** (Inbound messages from caregivers dropped) |
| **Glucose** | IMPLEMENTED | **PARTIALLY** (Text readings parsed; time-of-day ignored) |
| **Meals** | IMPLEMENTED | **YES** (Text meals parsed with taxonomy & confirm loop) |
| **Confirmation** | IMPLEMENTED | **YES** (Conversational confirmation loop works for meals) |
| **Timeline** | IMPLEMENTED | **PARTIALLY** (Visible in timeline, but channel provenance missing) |
| **P.L.A.T.E.** | IMPLEMENTED | **YES** (Participates in clinical observations & analytics) |
| **Outbound** | IMPLEMENTED | **PARTIALLY** (Works, but worker is not containerized) |
| **Templates** | SCAFFOLDED | **NO** (Hardcoded; no WABA synchronization) |
| **Media** | MISSING | **NO** (Photos and documents completely dropped) |
| **Voice** | MISSING | **NO** (Audio voice notes completely dropped) |
| **AI** | IMPLEMENTED | **YES** (Deterministic taxonomy parsing; safe) |
| **Evidence** | IMPLEMENTED | **PARTIALLY** (Observations feed into review, but lack channel tag) |
| **Audit** | IMPLEMENTED | **YES** (PHI-free immutable compliance logging) |
| **Deployment** | SCAFFOLDED | **NO** (Worker daemon missing from docker-compose) |
| **Testing** | PARTIALLY_IMPLEMENTED | **NO** (100% mocked; no live Meta sandbox verification) |

---

### Five Plain-Language Questions

#### 1. What can WhatsApp do right now?
If you manually run the worker script, a registered patient can send a text message in English or Hinglish containing a glucose reading (e.g., *"fasting 110"* or *"142"*) or a meal description (e.g., *"2 roti and dal"*). The system verifies the message signature, saves the glucose reading directly to the patient's chart, or creates a meal draft, sends a WhatsApp reply asking for confirmation, and confirms the meal once the patient replies *"YES"* or *"Haan"*.

#### 2. What cannot it do right now?
It cannot receive food photos, voice notes, or documents. It cannot handle messages from caregivers. It cannot verify that a WhatsApp number actually belongs to the patient who registered it. It does not run automatically in production because the background worker is not containerized.

#### 3. What parts are fake/mocked/scaffolded?
The identity resolver is scaffolded—it simply queries the patient table by phone number. All automated tests mock the Meta API using simulated HTTP responses and fake HMAC signatures. No live Meta environment has been integrated into continuous integration.

#### 4. What is required to connect real Meta WhatsApp?
You need: (a) a verified Meta Business Account with a WhatsApp Phone Number ID and System User token, (b) a containerized background worker in docker-compose, and (c) a public HTTPS URL (or tunnel) for the webhook callback endpoint.

#### 5. What should we build first after this audit?
Build a **verified WhatsApp identity model** (`whatsapp_identities` table with OTP verification) and **containerize the outbox worker process** in `docker-compose.production.yml`. Without these two foundations, connecting Meta would be both non-functional in production and clinically insecure.
