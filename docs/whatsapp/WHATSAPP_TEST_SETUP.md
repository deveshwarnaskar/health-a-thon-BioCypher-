# Meta WhatsApp Cloud API Test-Number Setup Guide

> **DEPRECATED for live operation.** The integration now runs on the REAL
> Meta-connected number **+91 99035 46271** (WABA `1999011964090146`). See
> `docs/whatsapp/WHATSAPP_LIVE_RUNBOOK.md` for the live 24x7 configuration.
> This doc documents the legacy sandbox setup only.

This guide details the exact environment setup for developing and testing the **THALI × P.L.A.T.E.** WhatsApp integration using Meta's Cloud API Test Number.

---

## 1. Meta Developer Configuration

The integration is registered under the following Meta Developer assets:

| Parameter | Value |
|---|---|
| **Meta App Name** | `THALI X P.L.A.T.E.` |
| **WhatsApp Business Account (WABA) ID** | `1622425102928569` |
| **Test Phone Number ID** | `1273367152534156` |
| **Graph API Version** | `v25.0` |
| **Meta Test Number Display** | `+1 555 025 4483` (Meta-provided sandbox number) |

---

## 2. Meta Sandbox Rules & Recipient Verification

Because this integration operates against Meta's Cloud API Test Number:
1. **Recipient Whitelisting**: Messages can **only** be sent to and received from phone numbers explicitly added to the "To" test phone numbers list in your [Meta Developer Dashboard](https://developers.facebook.com/).
2. **Verification Code**: When adding your personal or QA mobile number in the Meta Dashboard, Meta will send an OTP via WhatsApp. Verify the number before initiating tests.
3. **24-Hour Customer Care Window**: Once the verified test number sends an inbound message to the Meta test number, a 24-hour service session opens. Free-form text and interactive buttons can be sent without pre-approved utility templates during this window.

---

## 3. Local Environment Setup (`.env`)

All credentials must be placed exclusively into the root `.env` file (which is strictly gitignored). **Never commit credentials into Git.**

```dotenv
# Meta WhatsApp Cloud API Configuration
THALI_WHATSAPP__PHONE_NUMBER_ID=1273367152534156
THALI_WHATSAPP__BUSINESS_ACCOUNT_ID=1622425102928569
THALI_WHATSAPP__API_VERSION=v25.0
THALI_WHATSAPP__TEST_NUMBER_MODE=true

# Temporary / Regenerated Access Token from Meta Dashboard
THALI_WHATSAPP__ACCESS_TOKEN=EAAG...your_token_here...

# Webhook Security Credentials
THALI_WHATSAPP__VERIFY_TOKEN=thali-dev-verify-token
THALI_WHATSAPP__APP_SECRET=your_meta_app_secret_here
```

> **Note on Test Number Mode**:
> Setting `THALI_WHATSAPP__TEST_NUMBER_MODE=true` activates test-number developer mapping. If an incoming message originates from an unseeded phone number added in Meta's Developer Portal, the tenant resolver routes it safely to the primary active patient record for development and automated verification.

---

## 4. Starting the Backend & Outbox Worker

The THALI × P.L.A.T.E. WhatsApp architecture decouples webhook ingress from background command execution via the Transactional Outbox pattern.

### Terminal 1: Start FastAPI Backend
```bash
./.venv/bin/uvicorn backend.interfaces.http.app:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2: Start Transactional Outbox Worker
```bash
# Polling loop for local development
./.venv/bin/python -m backend.interfaces.cli.worker --poll
```

---

## 5. Webhook Tunneling (Meta -> Localhost)

Meta Cloud API requires a publicly reachable HTTPS endpoint for webhook delivery. Use `ngrok` or Cloudflare Tunnel:

```bash
ngrok http 8000
```

Copy the HTTPS forwarding URL (e.g. `https://your-domain.ngrok-free.app`) and configure it in the Meta Developer Dashboard:
- **Callback URL**: `https://your-domain.ngrok-free.app/api/v2/webhooks/whatsapp`
- **Verify Token**: `thali-dev-verify-token` (must match `THALI_WHATSAPP__VERIFY_TOKEN`)
- **Webhook Fields**: Subscribe to `messages`.
