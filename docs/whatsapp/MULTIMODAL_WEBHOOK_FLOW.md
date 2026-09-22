# WhatsApp Multimodal Webhook Intake Flow

## Detailed Technical Guide: From Meta Webhook to Canonical Persistence

---

## 1. Webhook Handshake & Verification

### GET `/api/v2/webhooks/whatsapp`
- Handshake endpoint queried by Meta during webhook subscription setup.
- Verifies `hub.mode == "subscribe"`.
- Validates `hub.verify_token` against configured token using **constant-time string comparison** (`hmac.compare_digest`).
- Echoes `hub.challenge` as plain text.

### POST `/api/v2/webhooks/whatsapp`
- Receiver endpoint for inbound messages, delivery receipts, and media.
- **Strict Verification Sequence**:
  1. Header `X-Hub-Signature-256` checked: must start with `sha256=`.
  2. HMAC-SHA256 computed over **raw request bytes** using `app_secret`.
  3. Validated via `hmac.compare_digest`. Any tampering or wrong secret raises HTTP 401.
  4. Only after valid signature is payload decoded as JSON.
  5. Dedup check: `SqlAlchemyWebhookReceiptStore.record()` writes `(provider, provider_message_id)` to `webhook_receipts`. Duplicate receipts are acknowledged with HTTP 202 and dropped immediately (replay protection).
  6. Outbox enqueue: `SqlAlchemyOutboxDomainEventPublisher` writes `WhatsAppMessageReceived` event into `domain_event_outbox` in the same transaction.
  7. Fast HTTP 202 Accepted response returned to Meta (<50ms).

---

## 2. Inbound Payload Metadata Normalization

The webhook parser extracts both text and media fields into `ParsedDelivery`:
- `provider_message_id`: WhatsApp Message ID (`wamid.HBgL...`).
- `source_phone`: Sender phone number in E.164 format.
- `media_type`: `"text"`, `"audio"`, `"image"`, `"video"`, `"document"`.
- `media_id`: Media object ID hosted on Meta's CDN.
- `mime_type`: MIME type declared by Meta (e.g. `audio/ogg; codecs=opus`, `image/jpeg`).
- `file_size_bytes`: Declared file size in bytes.
- `media_sha256`: Hash provided by Meta.
- `is_voice`: Boolean indicating PTT (push-to-talk) voice message.

---

## 3. Worker Ingestion Execution Flow

The background worker leases the outbox job and executes `WhatsAppIntakeHandler.handle()`:

```
Step 1: Phone Resolution
  SELECT tenant_id, id FROM patients WHERE phone = :phone
  - Unregistered: Sends polite guidance, fails permanently (zero retries)
  - Deactivated: Emits failure audit, denied domain access

Step 2: Media Retrieval Boundary
  WhatsAppChannelSender.download_media(media_id)
  - Queries https://graph.facebook.com/v21.0/{media_id}
  - Fetches binary payload bytes using Graph API access token

Step 3: MediaVault Encrypted Staging
  MediaVault.store(tenant_id, patient_id, media_type, message_id, payload_bytes, mime_type)
  - Encrypts via AES-256-GCM with 96-bit random nonce
  - Registers lease in memory

Step 4: Provider Adapter Execution
  - Voice -> SarvamSpeechToTextProvider -> Hinglish transcript
  - Image -> GeminiImageAnalysisProvider -> FoodItemCandidates + plate description

Step 5: MediaVault Cleanup
  - Disposed in finally: block upon use case completion
  - Background worker periodic retention sweep clears expired leases

Step 6: Parsing & Deterministic Calculations
  - parse_intake_text(text, stated_time or recorded_at)
  - Preserves user-stated time (chronology integrity)
  - Glucose -> IngestGlucoseReading
  - Meal -> LogMealDraft (with deterministic nutrition taxonomy)

Step 7: Interactive Confirmation Reply
  - Dispatches interactive button/text prompt to WhatsApp
```
