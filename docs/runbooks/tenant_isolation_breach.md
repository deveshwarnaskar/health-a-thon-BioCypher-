# Operational Runbook: Cross-Tenant Data Leakage & RLS Breach Alert

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
2. DPO audit of audit log records to quantify scope of affected records for regulatory disclosure.\n