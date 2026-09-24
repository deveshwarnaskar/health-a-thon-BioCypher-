#!/usr/bin/env python3
"""Gate 10P-G — Runbook Generator for 13 Mandatory Incident Scenarios.

Generates production-grade operational incident response runbooks adhering to
DevSecOps, SRE, and clinical governance standards.
"""

from pathlib import Path

RUNBOOKS_DIR = Path("docs/runbooks")
RUNBOOKS_DIR.mkdir(parents=True, exist_ok=True)

RUNBOOKS = {
    "api_outage.md": """# Operational Runbook: API Outage & Ingress Routing Failure

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
- Document post-mortem RCA within 24 hours under `docs/incident_reports/`.
""",

    "database_outage.md": """# Operational Runbook: PostgreSQL Database Primary Failure & Multi-AZ Failover

## 1. Metadata
- **Severity**: P0 (Complete Clinical Data Unavailability)
- **Service**: PostgreSQL 16 Cluster / AWS RDS Multi-AZ
- **RTO Target**: < 2 minutes (Automated), < 15 minutes (Manual)
- **RPO Target**: 0 seconds (Synchronous replication)
- **Escalation**: Principal Database Architect, SRE On-Call, Clinical Governance

---

## 2. Trigger & Detection
### Symptoms
- Backend API logs report `psycopg.OperationalError: could not connect to server: Connection refused`.
- API readiness probe `/health/readiness` fails with `database: UNHEALTHY`.
- Prometheus Alert: `PostgreSQLDown` or `RDSFailoverInitiated`.

### Log Query
```bash
grep -E "(OperationalError|connection timeout|remaining connection slots are reserved)" /var/log/thali/backend.log
```

---

## 3. Containment
1. If primary instance has frozen, verify whether automated RDS Multi-AZ failover has initiated.
2. Put transactional background workers in paused state to prevent poison-pill retries:
   ```bash
   docker compose -f deploy/production/docker-compose.production.yml stop worker
   ```
3. Ensure standby replica is healthy before forced promotion.

---

## 4. Diagnosis
1. Check RDS cluster status:
   ```bash
   aws rds describe-db-instances --db-instance-identifier thali-prod-postgres --region ap-south-1
   ```
2. Check replication lag on read replica:
   ```sql
   SELECT client_addr, state, sync_state, replay_lag FROM pg_stat_replication;
   ```
3. Check storage disk space exhaustion:
   ```sql
   SELECT pg_size_pretty(pg_database_size('thali_production'));
   ```

---

## 5. Recovery & Remediation
1. **Automated Multi-AZ Promotion**:
   - AWS RDS automatically updates DNS endpoint `db-prod.internal` to point to the promoted standby.
   - Wait for DNS propagation (~30-60s).
2. **Manual Failover Execution** (if automation stalled):
   ```bash
   aws rds reboot-db-instance --db-instance-identifier thali-prod-postgres --force-failover --region ap-south-1
   ```
3. **Database Restore Drill (Catastrophic Loss)**:
   - Run production-verified restore procedure:
     ```bash
     python3 scripts/rehearse_backup_restore.py
     ```
4. Restart application connection pools:
   ```bash
   kubectl rollout restart deployment/thali-backend-api -n production
   ```

---

## 6. Verification
1. Run database readiness check:
   ```bash
   PGPASSWORD=$PROD_DB_PASSWORD psql -h db-prod.internal -U thali_user -d thali_production -c "SELECT 1;"
   ```
2. Verify Row-Level Security policies active:
   ```sql
   SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
   ```
3. Check application readiness:
   ```bash
   curl -fv https://api.plate.thali.health/health/readiness
   ```

---

## 7. Escalation & Audit
- Confirm data loss is 0 (RPO = 0s) by comparing last committed transaction ID between replica and primary.
- Generate incident record including failover duration and RDS event log.
""",

    "redis_outage.md": """# Operational Runbook: Redis Cache & Rate Limiter Outage

## 1. Metadata
- **Severity**: P1 (Rate Limiting & Session Caching Degraded)
- **Service**: Redis 7.2 In-Memory Store / ElastiCache Cluster
- **Target MTTR**: < 5 minutes
- **Escalation**: SRE On-Call, Backend Platform Engineer

---

## 2. Trigger & Detection
### Symptoms
- API logs display `redis.exceptions.ConnectionError` or `TimeoutError`.
- Rate limiter fails open or closed according to security setting.
- Prometheus Alert: `RedisInstanceDown` or `RedisMemoryExhausted`.

---

## 3. Containment
1. If Redis is down, verify whether backend API runs with fail-open or fail-closed rate limiting.
2. In production, rate limiting must fail closed for high-risk endpoints (e.g. login, webhook) and fail open for clinical reads if required to maintain doctor workflow.
3. If memory is exhausted (100% maxmemory), adjust eviction policy to `volatile-lru` or restart node.

---

## 4. Diagnosis
1. Ping Redis server directly:
   ```bash
   redis-cli -h redis-prod.internal -p 6379 -a "$REDIS_PASSWORD" ping
   ```
2. Inspect memory and connected clients:
   ```bash
   redis-cli -h redis-prod.internal -p 6379 -a "$REDIS_PASSWORD" info memory
   redis-cli -h redis-prod.internal -p 6379 -a "$REDIS_PASSWORD" info clients
   ```

---

## 5. Recovery & Remediation
1. **Restart Redis Service**:
   ```bash
   docker compose -f deploy/production/docker-compose.production.yml restart redis
   ```
2. **Flush Corrupted Ephemeral Keys**:
   ```bash
   redis-cli -h redis-prod.internal -p 6379 -a "$REDIS_PASSWORD" flushdb async
   ```
3. Restart backend API workers to re-establish Redis connection pool:
   ```bash
   kubectl rollout restart deployment/thali-backend-api -n production
   ```

---

## 6. Verification
1. Verify Redis response:
   ```bash
   redis-cli -h redis-prod.internal -p 6379 -a "$REDIS_PASSWORD" ping
   # Expected: PONG
   ```
2. Verify rate-limiting enforcement on `/api/v2/auth/token`:
   ```bash
   for i in {1..20}; do curl -s -o /dev/null -w "%{http_code}\\n" https://api.plate.thali.health/health/liveness; done
   ```

---

## 7. Post-Incident
- Review memory growth patterns and tune `maxmemory` and `maxmemory-policy`.
""",

    "worker_outage.md": """# Operational Runbook: Transactional Outbox Background Worker Outage

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
   ```
""",

    "s3_outage.md": """# Operational Runbook: AWS S3 Document Storage Service Degradation

## 1. Metadata
- **Severity**: P1 (Document Upload & Clinical Lab Report Retrieval Blocked)
- **Service**: AWS S3 (`thali-production-documents-ap-south-1`)
- **Target MTTR**: < 15 minutes
- **Escalation**: SRE On-Call, Cloud Security Architect

---

## 2. Trigger & Detection
### Symptoms
- Clinical document upload fails with HTTP 500 / 503.
- Presigned URL generation times out or returns signature error.
- Prometheus Alert: `StorageErrorRateHigh` (>1% S3 failures over 5m).

---

## 3. Containment
1. Verify if AWS S3 regional incident is reported in `ap-south-1` on AWS Health Dashboard.
2. Enable local fallback object store if emergency document retention is active.
3. Queue upload metadata in transactional outbox for replay upon S3 recovery.

---

## 4. Diagnosis
1. Test bucket access and IAM permissions using AWS CLI:
   ```bash
   aws s3 ls s3://thali-production-documents-ap-south-1/ --region ap-south-1
   ```
2. Verify KMS key status (`alias/thali-production-docs-key`):
   ```bash
   aws kms describe-key --key-id alias/thali-production-docs-key --region ap-south-1
   ```
3. Verify bucket policy and SSE-KMS encryption enforcement.

---

## 5. Recovery & Remediation
1. If IAM role token expired, refresh ECS / EKS instance profile credentials.
2. If KMS key disabled, re-enable key via AWS Console or CLI:
   ```bash
   aws kms enable-key --key-id <key-id> --region ap-south-1
   ```
3. Re-test presigned URL issuance:
   ```bash
   .venv/bin/pytest tests/integration/test_gate_10p_g_golive_smoke.py -k test_smoke_12 -v
   ```

---

## 6. Verification
1. Execute test upload with tenant prefix validation:
   ```bash
   python3 -c "
   from backend.infrastructure.storage.s3_storage import S3ObjectStorage
   s = S3ObjectStorage('thali-production-documents-ap-south-1')
   s.put('tenants/test-tenant/patients/test-patient/test.txt', b'ok')
   assert s.exists('tenants/test-tenant/patients/test-patient/test.txt')
   "
   ```
""",

    "keycloak_outage.md": """# Operational Runbook: Keycloak Identity Provider Outage

## 1. Metadata
- **Severity**: P0 (Complete Authentication & Authorization Barrier)
- **Service**: Keycloak 24 IAM Cluster (`auth.plate.thali.health`)
- **Target MTTR**: < 5 minutes
- **Escalation**: Identity & Access Lead, SRE On-Call

---

## 2. Trigger & Detection
### Symptoms
- Clinicians and patients receive HTTP 401 Unauthorized across all mobile and web screens.
- Backend API logs indicate `JWKSError: Unable to fetch JWKS from https://auth.plate.thali.health/...`.
- Prometheus Alert: `KeycloakDown` or `JWKSFetchFailure`.

---

## 3. Containment
1. Verify if cached JWKS public keys in backend memory can continue validating existing tokens (grace period: 1 hour).
2. If Keycloak node has crashed, restart pod / container immediately.
3. Do NOT disable JWT signature validation or switch to insecure bypasses under any circumstances.

---

## 4. Diagnosis
1. Query Keycloak health endpoint:
   ```bash
   curl -fv https://auth.plate.thali.health/health/ready
   ```
2. Inspect Keycloak database connectivity:
   ```bash
   kubectl logs -l app=keycloak -n production --tail=200
   ```
3. Verify JWKS endpoint accessibility:
   ```bash
   curl -fv https://auth.plate.thali.health/realms/thali-production/protocol/openid-connect/certs
   ```

---

## 5. Recovery & Remediation
1. **Restart Keycloak Nodes**:
   ```bash
   kubectl rollout restart deployment/keycloak -n production
   ```
2. **JWKS Cache Reload**:
   - Backend automatically caches JWKS keys for 1 hour.
   - Force backend cache flush if keys were rotated:
     ```bash
     kubectl rollout restart deployment/thali-backend-api -n production
     ```
3. Re-import production realm if configuration was corrupted:
   ```bash
   # Using deploy/production/keycloak-production-realm.json
   ```

---

## 6. Verification
1. Run JWT token verification smoke test:
   ```bash
   .venv/bin/pytest tests/integration/test_gate_10p_g_golive_smoke.py -k test_smoke_01 -v
   ```
2. Authenticate admin user against Keycloak token endpoint and verify RS256 token issue.
""",

    "whatsapp_outage.md": """# Operational Runbook: WhatsApp Business API / Webhook Blackout

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
   ```
""",

    "ai_outage.md": """# Operational Runbook: Clinical AI Service & LLM Provider Degradation

## 1. Metadata
- **Severity**: P1 (AI Nutritional Summaries & Glycemic Risk Insights Degraded)
- **Service**: AI Service Adapter (OpenAI / Claude / Local MedGemma)
- **Target MTTR**: < 10 minutes
- **Escalation**: Clinical AI Lead, SRE On-Call, Medical Officer

---

## 2. Trigger & Detection
### Symptoms
- Meal photo nutrition extraction returns timeouts or upstream 5xx errors.
- AI review artifacts fail to generate; outbox jobs mark `RETRYABLE`.
- Prometheus Alert: `AIGenerationFailureRate` (>5% over 5m).

---

## 3. Containment
1. **CRITICAL CLINICAL INVARIANT**: The system must fail-safe to manual clinician review.
2. If AI is unavailable, patients can still submit manual text/photo logs and clinicians view raw entries.
3. Zero clinical decisions depend autonomously on AI; core clinical care continues uninterrupted.

---

## 4. Diagnosis
1. Check upstream LLM provider API status:
   ```bash
   curl -I https://api.openai.com/v1/models
   ```
2. Verify API rate limits or quota exhaustion on AI gateway.
3. Check circuit breaker status in backend logs (`AICircuitBreaker OPEN`).

---

## 5. Recovery & Remediation
1. Enable fallback local model or alternate cloud model via environment toggle:
   ```bash
   # Switch from primary to secondary provider
   export THALI_AI__MODEL="claude-3-5-sonnet"
   docker compose -f deploy/production/docker-compose.production.yml restart api
   ```
2. If provider is completely down, trip circuit breaker to fail gracefully with message:
   `"AI analysis currently unavailable; observation queued for manual clinician review."`

---

## 6. Verification
1. Run AI review workflow smoke test:
   ```bash
   .venv/bin/pytest tests/integration/test_gate_10p_g_golive_smoke.py -k test_smoke_08 -v
   ```
2. Verify clinical safety invariant: AI cannot self-approve or prescribe.
""",

    "certificate_expiry.md": """# Operational Runbook: TLS / SSL Certificate Expiration & Renewal

## 1. Metadata
- **Severity**: P0 (Browser & App Trust Blockout)
- **Service**: Let's Encrypt / AWS Certificate Manager (ACM)
- **Target MTTR**: < 10 minutes
- **Escalation**: Security Lead, SRE On-Call

---

## 2. Trigger & Detection
### Symptoms
- Mobile apps and web browsers display `NET::ERR_CERT_DATE_INVALID` or SSL handshake termination.
- Prometheus Alert: `TLSCertificateExpiringSoon` (<14 days remaining) or `TLSCertificateExpired`.

---

## 3. Containment
1. Identify failing certificate domain:
   ```bash
   echo | openssl s_client -servername api.plate.thali.health -connect api.plate.thali.health:443 2>/dev/null | openssl x509 -noout -dates
   ```

---

## 4. Diagnosis
1. Inspect Certbot / cert-manager logs:
   ```bash
   kubectl logs -l app=cert-manager -n cert-manager --tail=100
   ```
2. Verify Route 53 DNS-01 or HTTP-01 challenge completion.

---

## 5. Recovery & Remediation
1. **Force Manual Certbot Renewal (Ingress/Proxy)**:
   ```bash
   certbot renew --force-renewal
   ```
2. **AWS ACM Re-validation**:
   ```bash
   aws acm resend-validation-email --certificate-arn <arn> --region ap-south-1
   ```
3. Reload reverse proxy configuration:
   ```bash
   docker compose -f deploy/production/docker-compose.production.yml exec nginx nginx -s reload
   ```

---

## 6. Verification
1. Verify TLS handshake and certificate expiry date:
   ```bash
   curl -Iv https://api.plate.thali.health/health/liveness 2>&1 | grep -i "expire date"
   ```
""",

    "credential_compromise.md": """# Operational Runbook: Critical Credential & Secret Compromise

## 1. Metadata
- **Severity**: P0 (Immediate Security Emergency)
- **Scope**: Database credentials, JWT signing keys, AWS IAM keys, or API tokens
- **Target MTTR**: < 15 minutes (Revocation), < 30 minutes (Full Rotation)
- **Escalation**: Chief Information Security Officer (CISO), Data Protection Officer (DPO), SRE

---

## 2. Trigger & Detection
### Symptoms
- Secret leaked in git commit, container log, or unauthorized IP access detected.
- Alert from GitHub Secret Scanning, AWS GuardDuty, or Keycloak audit logs.

---

## 3. Containment
1. Immediately revoke compromised credential at the identity provider / IAM layer.
2. Invalidate all active user sessions in Keycloak:
   ```bash
   # Admin CLI token revocation
   kcadm.sh delete realms/thali-production/users/<user-id>/sessions
   ```
3. Restrict network access to database / S3 to VPC internal CIDR exclusively.

---

## 4. Diagnosis
1. Review access logs for compromised credential during the exposure window:
   ```sql
   SELECT * FROM audit_events 
   WHERE occurred_at >= '2026-09-18T00:00:00Z' 
   ORDER BY occurred_at DESC;
   ```

---

## 5. Recovery & Remediation
1. **Rotate PostgreSQL Password**:
   ```sql
   ALTER USER thali_user WITH PASSWORD 'NewSecureRandomPassword2026!#';
   ```
   Update AWS Secrets Manager and restart application pods.
2. **Rotate JWT RS256 Keypair in Keycloak**:
   - Generate new active RSA key in Keycloak Admin Realm Settings -> Keys.
   - Set old key to passive (verify-only for 1 hour grace period).
3. **Verify Configuration**:
   ```bash
   python3 scripts/verify_production_secrets.py
   ```

---

## 6. Verification & Legal Notification
1. Run security suite to confirm zero regressions:
   ```bash
   .venv/bin/pytest tests/security/test_gate_10p_g_production_security_rls.py -v
   ```
2. If patient data was accessed by unauthorized parties, initiate CERT-In / DPDP Act 2023 6-hour breach notification protocol.
""",

    "tenant_isolation_breach.md": """# Operational Runbook: Cross-Tenant Data Leakage & RLS Breach Alert

## 1. Metadata
- **Severity**: P0 (Critical Privacy & Data Isolation Failure)
- **Scope**: PostgreSQL Row-Level Security, Tenant Context Resolver
- **Target MTTR**: < 5 minutes (Containment), < 1 hour (RCA)
- **Escalation**: CISO, Data Protection Officer, Principal Architect

---

## 2. Trigger & Detection
### Symptoms
- Security test failure in `test_gate_10p_g_production_security_rls.py`.
- Audit logs report actor from Tenant A accessing Tenant B `patient_id`.
- Prometheus Alert: `CrossTenantAccessAttempt` or `RLSViolationDetected`.

---

## 3. Containment
1. If systemic RLS failure detected, immediately revoke API access or put API in maintenance mode:
   ```bash
   kubectl scale deployment/thali-backend-api -n production --replicas=0
   ```
2. Verify if `app.current_tenant_id` session setting is missing or bypassed.

---

## 4. Diagnosis
1. Inspect RLS policy enablement on all clinical tables:
   ```sql
   SELECT schemaname, tablename, rowsecurity 
   FROM pg_tables 
   WHERE schemaname = 'public';
   ```
2. Verify RLS policy definition:
   ```sql
   SELECT * FROM pg_policies WHERE schemaname = 'public';
   ```
3. Trace the query execution plan with tenant context:
   ```sql
   SET LOCAL app.current_tenant_id = '00000000-0000-0000-0000-000000000001';
   EXPLAIN ANALYZE SELECT * FROM patients;
   ```

---

## 5. Recovery & Remediation
1. Re-apply idempotent RLS policies:
   ```bash
   python3 scripts/rehearse_database_migration.py
   ```
2. Verify UnitOfWork tenant scoping:
   ```bash
   .venv/bin/pytest tests/security/test_gate_10p_g_production_security_rls.py -k test_patient_cross_tenant_isolation -v
   ```

---

## 6. Verification & Reporting
1. Run multi-tenant isolation suite:
   ```bash
   .venv/bin/pytest tests/security/test_gate_10p_g_production_security_rls.py -v
   ```
2. DPO audit of audit log records to quantify scope of affected records for regulatory disclosure.
""",

    "data_corruption.md": """# Operational Runbook: Clinical Record Corruption & Point-in-Time Recovery

## 1. Metadata
- **Severity**: P0 (Clinical Record Fidelity Loss)
- **Scope**: Database Corrupted Records, Failed Transaction Partial Writes
- **Target MTTR**: < 30 minutes
- **Escalation**: Database Lead, Clinical Safety Officer, SRE

---

## 2. Trigger & Detection
### Symptoms
- Data consistency check or clinical audit detects corrupted patient observations.
- Foreign key violation or mismatched UHID references.
- Prometheus Alert: `DataIntegrityCheckFailed`.

---

## 3. Containment
1. Place affected tenant in read-only mode to prevent propagation of corrupted records.
2. Identify timestamp $T_{\\text{corrupt}}$ when corruption began.

---

## 4. Diagnosis
1. Query `audit_events` table for mutations within the corruption window:
   ```sql
   SELECT * FROM audit_events 
   WHERE occurred_at >= NOW() - INTERVAL '2 hours' 
   ORDER BY occurred_at DESC;
   ```
2. Verify WAL log integrity and identify clean point-in-time recovery target.

---

## 5. Recovery & Remediation
1. **Point-in-Time Recovery (PITR)**:
   - Restore database to timestamp $T_{\\text{clean}} = T_{\\text{corrupt}} - 1\\text{s}$ using RDS PITR:
     ```bash
     aws rds restore-db-instance-to-point-in-time \
       --source-db-instance-identifier thali-prod-postgres \
       --target-db-instance-identifier thali-prod-restored \
       --restore-time 2026-09-18T12:00:00Z \
       --region ap-south-1
     ```
2. Run backup/restore verification script:
   ```bash
   python3 scripts/rehearse_backup_restore.py
   ```
3. Replay transactional outbox events occurring after $T_{\\text{clean}}$ to reconstruct clean data.

---

## 6. Verification
1. Validate patient and observation counts against audit ledger.
2. Execute smoke test suite:
   ```bash
   .venv/bin/pytest tests/integration/test_gate_10p_g_golive_smoke.py -v
   ```
""",

    "failed_migration.md": """# Operational Runbook: Alembic Database Migration Failure & Fast Rollback

## 1. Metadata
- **Severity**: P0 during deployment window
- **Scope**: Alembic Schema Revisions, PostgreSQL Table Locks
- **Target MTTR**: < 2 minutes
- **Escalation**: Release Engineer, Database Lead, SRE On-Call

---

## 2. Trigger & Detection
### Symptoms
- Deployment pipeline halts at `alembic upgrade head` with SQL execution error or deadlock.
- Schema migration lock blocks web traffic (`Lock timeout`).
- Prometheus Alert: `MigrationFailed` or `DatabaseLockTimeout`.

---

## 3. Containment
1. Terminate the blocking migration transaction immediately.
2. Do NOT proceed with application container deployment if database schema is in inconsistent state.

---

## 4. Diagnosis
1. Check current Alembic revision in PostgreSQL:
   ```sql
   SELECT version_num FROM alembic_version;
   ```
2. Inspect active table locks:
   ```sql
   SELECT pid, relation::regclass, mode, granted 
   FROM pg_locks 
   WHERE NOT granted;
   ```

---

## 5. Recovery & Remediation
1. **Automated Downgrade Drill**:
   - Revert schema to parent revision using Alembic:
     ```bash
     alembic downgrade -1
     # Or run verified rehearsal procedure
     python3 scripts/verify_staging_rollback.py
     ```
2. **Clean State Restoration**:
   - Verify all 17 clinical and ops tables match baseline schema:
     ```bash
     python3 scripts/rehearse_database_migration.py
     ```
3. Re-deploy previous known-stable application image:
   ```bash
   kubectl rollout undo deployment/thali-backend-api -n production
   ```

---

## 6. Verification
1. Confirm Alembic version matches target clean state.
2. Run migration drill verification:
   ```bash
   python3 scripts/verify_staging_rollback.py
   ```
3. Run integration smoke tests:
   ```bash
   .venv/bin/pytest tests/integration/test_gate_10p_g_golive_smoke.py -v
   ```
""",
}

for filename, content in RUNBOOKS.items():
    filepath = RUNBOOKS_DIR / filename
    filepath.write_text(content.strip() + "\\n", encoding="utf-8")
    print(f"✓ Generated {filepath}")

print(f"\\nSuccessfully generated all {len(RUNBOOKS)} operational runbooks in {RUNBOOKS_DIR}")
