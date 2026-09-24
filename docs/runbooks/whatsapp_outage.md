# Operational Runbook: WhatsApp Business API / Webhook Blackout

## 1. Metadata
- **Severity**: P1 (Patient Adherence Reminders & Conversational Logging Degraded)
- **Service**: Meta Cloud API / WhatsApp Gateway Integration
- **Target MTTR**: < 15 minutes
- **Escalation**: Messaging Lead, SRE On-Call

---

## 2. Trigger & Detection
### Symptoms
- Inbound WhatsApp messages not appearing in observation feed.
- Outbound adherence reminders accumulating in outbox queue as `RETRYABLE`.
- Prometheus Alert: `WhatsAppDeliveryFailureRate` (>5% failures over 10m).

---

## 3. Containment
1. Check Meta Developer Portal for WhatsApp Cloud API system outages.
2. Inbound webhooks must return HTTP 200/202 to Meta within 3 seconds to avoid webhook subscription suspension.
3. Outbound messages retry with exponential backoff via outbox worker; do not drop messages.

---

## 4. Diagnosis
1. Verify Meta webhook signature validation (`X-Hub-Signature-256`):
   ```bash
   grep -E "(HMAC|signature mismatch|invalid webhook)" /var/log/thali/backend.log
   ```
2. Inspect access token expiry in AWS Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value --secret-id thali/production/whatsapp-token --region ap-south-1
   ```

---

## 5. Recovery & Remediation
1. If access token expired, regenerate System User Access Token in Meta Business Manager and update Secrets Manager.
2. Restart backend worker to load refreshed token:
   ```bash
   docker compose -f deploy/production/docker-compose.production.yml restart worker
   ```
3. Re-process queued WhatsApp notifications:
   ```bash
   .venv/bin/pytest tests/integration/test_gate_10p_g_golive_smoke.py -k test_smoke_11 -v
   ```

---

## 6. Verification
1. Verify inbound webhook receipt test:
   ```bash
   .venv/bin/pytest tests/security/test_whatsapp_webhook.py -v
   ```\n