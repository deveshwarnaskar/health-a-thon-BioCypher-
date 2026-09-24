# Operational Runbook: Critical Credential & Secret Compromise

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
2. If patient data was accessed by unauthorized parties, initiate CERT-In / DPDP Act 2023 6-hour breach notification protocol.\n