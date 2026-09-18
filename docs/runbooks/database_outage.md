# Operational Runbook: PostgreSQL Database Primary Failure & Multi-AZ Failover

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
- Generate incident record including failover duration and RDS event log.\n