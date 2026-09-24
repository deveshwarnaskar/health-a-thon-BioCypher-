# WhatsApp Webhook Specification & Implementation

This document describes the design, security protocols, and payload handling for the **THALI × P.L.A.T.E.** WhatsApp Webhook endpoint.

---

## 1. Routes & Contract Surface

The WhatsApp webhook is exposed under `/api/v2/webhooks/whatsapp`:

| Method | Endpoint | Purpose | Authorization |
|---|---|---|---|
| `GET` | `/api/v2/webhooks/whatsapp` | Meta challenge verification handshake | Query token constant-time comparison |
| `POST` | `/api/v2/webhooks/whatsapp` | Inbound message and status receiver | HMAC-SHA256 signature over raw request body |

---

## 2. Inbound Processing Pipeline

Every incoming webhook POST request is processed through a strict security and reliability pipeline:

```text
Incoming POST Bytes
       │
       ▼
[1] HMAC-SHA256 Signature Verification
    (X-Hub-Signature-256 checked in constant time over raw bytes)
       │  Failed ──► 401 Unauthorized (Raw bytes never logged)
       ▼
[2] JSON Parse & Delivery Extraction
    (provider_message_id, source_phone, event_type, metadata)
       │  Malformed ──► 400 Bad Request
       ▼
[3] Rate Limit Evaluation (Webhook Tier, Fail-Open)
       │  Exceeded ──► 429 Too Many Requests
       ▼
[4] Transactional Replay Deduplication & Outbox Enqueue (Single DB Commit)
    • SqlAlchemyWebhookReceiptStore (7-day retention)
    • SqlAlchemyOutboxDomainEventPublisher (WhatsAppMessageReceived)
       │  Duplicate ──► ACK 202 Accepted (Dropped, zero duplicate work)
       │  DB Failure ──► 503 Service Unavailable (Meta will retry)
       ▼
[5] ACK 202 Accepted (Delivery acknowledged in < 200ms)
```

---

## 3. Verification Handshake (`GET`)

When configuring the webhook in the Meta Developer Dashboard, Meta sends a GET request:

```http
GET /api/v2/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=thali-dev-verify-token&hub.challenge=CHALLENGE_STRING HTTP/1.1
```

### Handler Invariants:
- `hub.mode` must equal `"subscribe"`.
- `hub.verify_token` is compared against `THALI_WHATSAPP__VERIFY_TOKEN` using constant-time comparison (`hmac.compare_digest`).
- On success, returns HTTP 200 with raw challenge body `{"challenge": "CHALLENGE_STRING"}`.
- On mismatch, returns HTTP 403 Forbidden.

---

## 4. Cryptographic Signature Verification (`POST`)

Meta signs every webhook payload with the application's App Secret:

```http
POST /api/v2/webhooks/whatsapp HTTP/1.1
Host: api.thaliplate.care
Content-Type: application/json
X-Hub-Signature-256: sha256=d3b07384d113edec49eaa6238ad5ff00...
```

### Security Gates:
- The signature is calculated as `HMAC_SHA256(raw_bytes, app_secret)`.
- The verification occurs **before** any JSON deserialization or memory allocation.
- Constant-time comparison ensures zero susceptibility to timing side-channels.
- If missing or invalid, an immediate HTTP 401 is returned. The raw body is **never** logged, guaranteeing zero credential or PHI leakage.

---

## 5. Supported Inbound Payloads

The webhook delivery parser supports all standard Meta WhatsApp Cloud API formats:

### A. Free-Text Messages
```json
{
  "from": "919876543210",
  "id": "wamid.HBgLMDExMQ==",
  "timestamp": "1710000000",
  "type": "text",
  "text": { "body": "140 fasting" }
}
```
*Extracted: `text = "140 fasting"`, `message_type = "text"`.*

### B. Interactive Button Replies
```json
{
  "from": "919876543210",
  "id": "wamid.BTN_REPLY",
  "timestamp": "1710000010",
  "type": "interactive",
  "interactive": {
    "type": "button_reply",
    "button_reply": {
      "id": "confirm_yes",
      "title": "Yes / Haan"
    }
  }
}
```
*Extracted: `text = "Yes / Haan"`, `interactive_reply_id = "confirm_yes"`, `message_type = "interactive"`.*

### C. Media Messages (Images with Captions)
```json
{
  "from": "919876543210",
  "id": "wamid.MEDIA_IMG",
  "timestamp": "1710000020",
  "type": "image",
  "image": {
    "id": "media-file-999",
    "mime_type": "image/jpeg",
    "caption": "plate of food"
  }
}
```
*Extracted: `text = "plate of food"`, `media_id = "media-file-999"`, `message_type = "image"`.*

### D. Provider Status Receipts
```json
{
  "statuses": [
    {
      "id": "wamid.STATUS_MSG",
      "status": "delivered",
      "timestamp": "1710000030",
      "recipient_id": "919876543210"
    }
  ]
}
```
*Extracted: `event_type = "status_received"`, acknowledged without clinical side-effects.*
