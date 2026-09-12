# Architectural Rules & Invariants

## 1. Store-First, Decoupled AI Invariant (Webhooks)
- **Zero-Latency Inbound Webhooks**: The Meta WhatsApp webhook endpoint (POST /api/v1/webhooks/whatsapp) must NEVER execute external LLM calls (Gemini) synchronously within the HTTP request/response cycle.
- **Durable Capture First**: Webhook handlers must immediately persist incoming payloads to durable storage (raw_inbound) and return HTTP 200 to Meta within < 500ms.
- **Decoupled Reasoning**: AI reasoning (intent classification, food extraction, conversational replies) must operate asynchronously on the stored database records.
- **Outbound Dispatch**: Once Gemini finishes reasoning on the stored record, outbound WhatsApp replies are dispatched independently via backend.send() and logged to outbound.
- **Resilience**: If an external LLM fails, times out, or rate-limits, the patient's message is already safely stored in the database, visible to the doctor on the dashboard, and can be retried or handled gracefully without losing data or breaking the webhook connection.
