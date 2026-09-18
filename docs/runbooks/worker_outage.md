# Operational Runbook: Transactional Outbox Background Worker Outage

## 1. Metadata
- **Severity**: P1 (Delayed Clinical Event Dispatch & Notifications)
- **Service**: `thali-outbox-worker`
- **Target MTTR**: < 10 minutes
- **Escalation**: Backend Platform Engineer, SRE On-Call

---

## 2. Trigger & Detection
### Symptoms
- Notifications (WhatsApp, push) are not delivered to patients.
- Domain events remain in `pending` or `processing` state without publishing.
- Prometheus Alert: `OutboxQueueDepthHigh` (>100 pending events for >5m) or `OutboxWorkerHung`.

### PromQL Verification
```promql
outbox_pending_depth > 100
outbox_processing_depth > 50
```

---

## 3. Containment
1. Check if poisoned events are causing infinite retries or crashes.
2. Check for worker lease locks stuck in `processing` state:
   ```sql
   SELECT event_id, event_type, status, locked_at, locked_by, retry_count 
   FROM domain_event_outbox 
   WHERE status = 'processing' AND locked_at < now() - interval '5 minutes';
   ```

---

## 4. Diagnosis
1. Inspect worker container logs:
   ```bash
   docker logs thali-production-worker --tail 200
   ```
2. Identify failing event handlers (e.g. WhatsApp API rate-limited, SMTP failure, S3 failure).

---

## 5. Recovery & Remediation
1. **Reclaim Stuck Leases**:
   - Outbox worker store automatically frees expired leases (`locked_at < now() - lease_seconds`).
   - If manual unlock needed:
     ```sql
     UPDATE domain_event_outbox 
     SET status = 'pending', locked_by = NULL, locked_at = NULL 
     WHERE status = 'processing' AND locked_at < now() - interval '5 minutes';
     ```
2. **Dead-Letter Poison Events**:
   ```sql
   UPDATE domain_event_outbox 
   SET status = 'dead_letter', last_error = 'Manual quarantine of poison event' 
   WHERE retry_count > 5 AND status = 'pending';
   ```
3. Restart worker process:
   ```bash
   docker compose -f deploy/production/docker-compose.production.yml restart worker
   ```

---

## 6. Verification
1. Check outbox queue depth in Prometheus:
   ```promql
   outbox_pending_depth == 0
   ```
2. Verify end-to-end processing with smoke test:
   ```bash
   .venv/bin/pytest tests/integration/test_gate_10p_g_golive_smoke.py -k test_smoke_14 -v
   ```\n