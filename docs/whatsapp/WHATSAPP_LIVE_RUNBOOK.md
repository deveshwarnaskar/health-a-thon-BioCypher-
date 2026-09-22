# Meta WhatsApp Cloud API Live Runbook (24x7)

Live production configuration for the **THALI x P.L.A.T.E.** WhatsApp integration
using the real Meta-connected number **+91 99035 46271**.

| Parameter | Value |
|---|---|
| **Meta App Name** | `THALI X P.L.A.T.E.` |
| **WhatsApp Business Account (WABA) ID** | `1999011964090146` |
| **Real Phone Number** | `+91 99035 46271` |
| **Phone Number ID** | numeric ID of `+91 99035 46271` (from API Setup) |
| **Graph API Version** | `v25.0` |
| **Meta Display Name** | `THALI X P.L.A.T.E.` |

---

## 1. Required Credentials (Meta Developer Dashboard)

Populate these in the root `.env`:

```dotenv
THALI_WHATSAPP__PHONE_NUMBER_ID=<phone number ID of +91 99035 46271>
THALI_WHATSAPP__BUSINESS_ACCOUNT_ID=1999011964090146
THALI_WHATSAPP__API_VERSION=v25.0
THALI_WHATSAPP__TEST_NUMBER_MODE=false

# Long-lived System User token (NOT the temporary 24h token)
THALI_WHATSAPP__ACCESS_TOKEN=<long-lived token>

# Meta App Secret (from App Settings > Basic) — enables strict X-Hub-Signature-256 verification
THALI_WHATSAPP__APP_SECRET=<meta app secret>

# Must EXACTLY match the Verify Token entered in the Meta webhook configuration
THALI_WHATSAPP__VERIFY_TOKEN=<same verify token registered in Meta>
```

> **Long-lived token (24x7):** generate a System User in
> `Meta Business Suite > Business Settings > System Users`, assign the
> WhatsApp business-management permission, and generate a token that never
> expires. The temporary "API Setup" token expires in 24 hours and will break
> live operation.

---

## 2. Webhook (Meta must reach a public HTTPS endpoint)

Callback URL registered in Meta Developer Dashboard:

```
https://<your-public-host>/api/v2/webhooks/whatsapp
```

- **Verify Token**: must match `THALI_WHATSAPP__VERIFY_TOKEN`.
- **Webhook Fields**: subscribe to `messages`.
- The endpoint must be **public HTTPS** (deployed host or a persistent tunnel —
  Meta rejects HTTP and non-public hosts; a restarting local `ngrok` is not
  reliable for 24x7).

---

## 3. Process Checklist (24x7)

- [ ] Backend serving `:8000` (public HTTPS proxy terminates TLS in front).
- [ ] Outbox worker running: `python -m backend.interfaces.cli.worker --poll`
- [ ] `THALI_WHATSAPP__TEST_NUMBER_MODE=false` (unregistered senders are refused, never routed to a random patient).
- [ ] `THALI_WHATSAPP__APP_SECRET` set so webhook HMAC is enforced (real secret, not `dev-webhook-secret`).
- [ ] Long-lived access token installed; no dependency on a 24-hour temporary token.
- [ ] Mobile `EXPO_PUBLIC_WHATSAPP_BUSINESS_NUMBER=919903546271` so the app opens chat with the real number.

---

## 4. Message Flow (Reference)

Inbound WhatsApp → Meta → webhook (HMAC verified) → replay dedup → outbox →
worker → sender resolver (phone → patient) → intent firewall → AI (Sarvam) →
reply via Graph API `/{phone_number_id}/messages`.

Unregistered senders receive the polite "not registered" guidance and are never
matched to another patient.