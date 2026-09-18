# Operational Runbook: Keycloak Identity Provider Outage

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
2. Authenticate admin user against Keycloak token endpoint and verify RS256 token issue.\n