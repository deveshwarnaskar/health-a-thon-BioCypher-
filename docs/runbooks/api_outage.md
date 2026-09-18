# Operational Runbook: API Outage & Ingress Routing Failure

## 1. Metadata
- **Severity**: P0 (Critical Service Interruption)
- **Service**: `thali-backend-api` (FastAPI / Uvicorn ASGI cluster)
- **Target MTTR**: < 5 minutes
- **Escalation**: On-Call SRE (`sre-oncall@plate.thali.health`), Platform Lead, Clinical Safety Lead

---

## 2. Trigger & Detection
### Symptoms
- Ingress ALB / Envoy reports HTTP 502 / 503 / 504 surges.
- Uptime probe `GET https://api.plate.thali.health/health/liveness` returns non-200 or times out (>2000ms).
- Prometheus Alert: `ApiHighErrorRate` (>5% 5xx over 2m) or `ApiInstanceDown` (replicas < 2).

### PromQL Verification
```promql
sum(rate(http_requests_total{status=~"5.."}[2m])) / sum(rate(http_requests_total[2m])) * 100 > 5
sum(up{job="thali-backend-api"}) < 2
```

---

## 3. Containment
1. If outage affects only one AZ, route traffic via Route 53 / ALB target group weighting away from unhealthy zone.
2. If memory leak or deadlock causes worker starvation, initiate rolling pod restart:
   ```bash
   kubectl rollout restart deployment/thali-backend-api -n production
   # Or docker compose
   docker compose -f deploy/production/docker-compose.production.yml restart api
   ```
3. Enable Cloudflare / ALB Maintenance Page for patient web requests if total downtime exceeds 3 minutes.

---

## 4. Diagnosis
1. Inspect recent deployment logs and OOM kills:
   ```bash
   kubectl describe pods -l app=thali-backend-api -n production | grep -E "(OOMKilled|ExitCode|Last State)"
   kubectl logs -l app=thali-backend-api -n production --tail=200 --prefix
   ```
2. Check upstream database and Redis connectivity:
   ```bash
   nc -zv db-prod.internal 5432
   nc -zv redis-prod.internal 6379
   ```
3. Verify connection pool exhaustion in Prometheus:
   ```promql
   sqlalchemy_pool_busy_connections{job="thali-backend-api"} >= 30
   ```

---

## 5. Recovery & Remediation
1. **OOM / Worker Starvation**: Increase memory limits or worker count:
   ```bash
   kubectl set resources deployment thali-backend-api -n production --limits=memory=4Gi,cpu=2000m
   ```
2. **Bad Release / Faulty Migration**: Execute rapid image rollback:
   ```bash
   kubectl rollout undo deployment/thali-backend-api -n production
   ```
3. **Database Locks**: If blocking queries lock ASGI workers, terminate long-running idle transactions on PostgreSQL primary:
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'idle in transaction' AND state_change < now() - interval '2 minutes';
   ```

---

## 6. Verification
1. Probe liveness and readiness endpoints:
   ```bash
   curl -fv https://api.plate.thali.health/health/liveness
   curl -fv https://api.plate.thali.health/health/readiness
   ```
2. Execute Go-Live Smoke Test Suite in staging/production rehearsal mode:
   ```bash
   .venv/bin/pytest tests/integration/test_gate_10p_g_golive_smoke.py -v
   ```
3. Verify Prometheus error rate returns to 0.0%:
   ```promql
   sum(rate(http_requests_total{status=~"5.."}[5m])) == 0
   ```

---

## 7. Escalation & Audit
- If outage exceeds 15 minutes, notify Chief Medical Officer (CMO) per clinical risk protocol.
- Document post-mortem RCA within 24 hours under `docs/incident_reports/`.\n