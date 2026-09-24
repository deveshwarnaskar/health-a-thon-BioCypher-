# AI & Multimodal Intelligence System

## THALI × P.L.A.T.E. Clinical Intelligence Architecture

---

## 1. Overview

The Artificial Intelligence layer in **THALI × P.L.A.T.E.** is strictly designed as an **assistive, evidence-first signal processing and summarization subsystem**. It is completely decoupled from canonical clinical state transitions and deterministic physiological mathematics.

The subsystem serves two complementary roles:
1. **Multimodal Ingestion (Signal Conversion)**: Converts unstructured voice notes and meal photos from WhatsApp into normalized, structured candidates that pass through deterministic parsers and patient confirmation loops.
2. **Clinical Review Drafts (Physician Review Preparation)**: Analyzes longitudinal glycemic telemetry, correlates it with meal logs and physical symptoms, and drafts structured SOAP review packages (`AIReviewArtifact`) for licensed doctors in Doctor P.L.A.T.E.

---

## 2. Core Architectural Philosophy

```
[Raw Multimodal Signal]
        │ (Audio bytes, Image bytes, Text)
        ▼
[Provider-Neutral AI Seam]
        │ (Sarvam, Gemini, Local Fallbacks)
        ▼
[Candidate Data / Draft Note]
        │
        ├── Ingestion: Candidate passes through Deterministic Parsers & Confirmation Loop
        └── Clinical Draft: Artifact in "GENERATED" state awaiting Doctor APPROVE / EDIT / REJECT
```

### Invariants:
- **Zero Autonomous Clinical Action**: AI never diagnoses, prescribes, titrates, or modifies clinician orders.
- **Deterministic Mathematics Precedes AI**: TIR, TAR, TBR, Mean Glucose, SD, CV%, GMI, and estimated A1c are computed strictly by deterministic algorithms (`calculate_glycemic_metrics`).
- **Deterministic Nutrition Precedes Meal Persistence**: Carbohydrates, glycemic index, and dietary classifications are computed by the Indian Food Composition Table (ICMR-NIN) taxonomy (`classify_text` and `estimate_nutrition`), never by LLM hallucinations.

---

## 3. Subsystem Index

- [Multimodal Architecture & Ports](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master%20copy/docs/ai/MULTIMODAL_ARCHITECTURE.md)
- [Sarvam AI Indic Platform Integration](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master%20copy/docs/ai/SARVAM_INTEGRATION.md)
- [Gemini Vision Meal Analysis Integration](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master%20copy/docs/ai/GEMINI_VISION_INTEGRATION.md)
- [Clinical Safety, Autonomy & Governance](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master%20copy/docs/ai/SAFETY_AND_GOVERNANCE.md)
