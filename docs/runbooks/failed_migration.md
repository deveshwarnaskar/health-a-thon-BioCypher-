# Operational Runbook: Alembic Database Migration Failure & Fast Rollback

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
   ```\n