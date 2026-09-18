# Operational Runbook: AWS S3 Document Storage Service Degradation

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
   ```\n