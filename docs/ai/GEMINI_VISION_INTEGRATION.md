# Gemini Vision Meal Analysis Integration

## Image Telemetry & Food Candidate Extraction

---

## 1. Overview

Meal photography sent by patients via WhatsApp is analyzed using Google Gemini 1.5 Flash through the provider-neutral `ImageAnalysisProvider` protocol. The integration is implemented in [`backend/infrastructure/ai/gemini_image_analysis.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master%20copy/backend/infrastructure/ai/gemini_image_analysis.py).

---

## 2. Strict Invariants

1. **Candidate Extraction Only**:
   - The vision adapter extracts **item names** and **visual portions** (e.g. `roti`, `2 roti`, `dal`, `1 katori`).
   - The adapter **NEVER estimates or outputs nutrition numbers** (carbs, calories, fats, proteins, glycemic index).
2. **Deterministic Round-Trip Required**:
   - The vision model's output is mapped to a Hinglish plate description string (e.g., `"2 roti and dal"`).
   - This string is then parsed through the deterministic Indian Food Composition Tables (ICMR-NIN) taxonomy (`backend/infrastructure/parsing/nutrition_taxonomy.py`).
   - Only the deterministic taxonomy calculates carbohydrate grams and glycemic tier.
3. **No Autonomous State Mutation**:
   - A meal photograph creates a `MealObservation` in `PENDING` state.
   - It **never derives a GlucoseObservation**.
   - It **never mutates a MedicationPlan**.

---

## 3. Vision Prompt Structure

Gemini is invoked using pure REST via Python standard library `urllib.request` (no heavy proprietary SDK required). The system prompt is strictly constrained:

```text
This is a meal photo taken on a phone in India. List the food items you can 
clearly see and a rough serving size for each. Verbatim JSON ONLY in this 
shape: {"items":[{"name":"<Hinglish food name like \"2 roti\" or \"dal\" or 
\"kofta curry\">","portion":"<serving label like \"1 katori\" or \"2 roti\">"}], 
"description":"<one short Hinglish plate description for the whole meal>",
"confidence":"high|medium|low"}. If the photo is not food or nothing can be 
identified, return {"items":[],"description":"","confidence":"low"}. 
Do NOT return or estimate any nutrition values.
```

---

## 4. Fail-Safe Behavior & Low Confidence Handling

- If Gemini returns empty items, `unidentifiable=True`, or `confidence="low"`, the intake handler executes `_safe_media_guidance()`:
  - Responds to the patient with `LOW_CONFIDENCE_GUIDANCE`:
    > *"Main photo mein khana sahi se pehchan nahi paya. Kripya thoda clear photo bhejein ya khane ka naam likh kar bhejein (jaise: '2 roti dal'). Aapki sahi health record ke liye confirm hona zaroori hai."*
  - Emits a `MULTIMODAL_SAFE_FALLBACK` audit event.
  - Increments `image_pipeline_failure_total{kind="unidentifiable"}`.
  - Zero unverified meal records are written to PostgreSQL.
