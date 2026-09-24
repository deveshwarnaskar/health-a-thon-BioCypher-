# Operational Runbook: Redis Cache & Rate Limiter Outage

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
   for i in {1..20}; do curl -s -o /dev/null -w "%{http_code}\n" https://api.plate.thali.health/health/liveness; done
   ```

---

## 7. Post-Incident
- Review memory growth patterns and tune `maxmemory` and `maxmemory-policy`.\n