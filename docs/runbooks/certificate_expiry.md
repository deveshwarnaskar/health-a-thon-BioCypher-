# Operational Runbook: TLS / SSL Certificate Expiration & Renewal

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
   ```\n