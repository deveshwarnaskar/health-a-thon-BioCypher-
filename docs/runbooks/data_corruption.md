# Operational Runbook: Clinical Record Corruption & Point-in-Time Recovery

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
2. Identify timestamp $T_{\text{corrupt}}$ when corruption began.

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
   - Restore database to timestamp $T_{\text{clean}} = T_{\text{corrupt}} - 1\text{s}$ using RDS PITR:
     ```bash
     aws rds restore-db-instance-to-point-in-time        --source-db-instance-identifier thali-prod-postgres        --target-db-instance-identifier thali-prod-restored        --restore-time 2026-09-18T12:00:00Z        --region ap-south-1
     ```
2. Run backup/restore verification script:
   ```bash
   python3 scripts/rehearse_backup_restore.py
   ```
3. Replay transactional outbox events occurring after $T_{\text{clean}}$ to reconstruct clean data.

---

## 6. Verification
1. Validate patient and observation counts against audit ledger.
2. Execute smoke test suite:
   ```bash
   .venv/bin/pytest tests/integration/test_gate_10p_g_golive_smoke.py -v
   ```\n