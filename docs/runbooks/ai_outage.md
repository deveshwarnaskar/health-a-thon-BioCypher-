# Operational Runbook: Clinical AI Service & LLM Provider Degradation

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
2. Verify clinical safety invariant: AI cannot self-approve or prescribe.\n