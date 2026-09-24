# THALI × P.L.A.T.E. Multimodal WhatsApp Intake

## Telemetry & Household Assistive Logbook for Interventions (THALI) × Patient Logbook for Assistive Telemetry and Excursion (P.L.A.T.E.)

---

## 1. Architectural Overview & Philosophy

The multimodal intake system extends the existing production-oriented WhatsApp channel with **provider-neutral voice and image telemetry capture**. It bridges ambient, household health logging (voice notes in Hinglish/Indic dialects and meal photographs) to the structured clinical database of the hospital while strictly adhering to core clinical safety invariants.

### Key Architectural Invariant: The 13-Stage Data Traversal

$$\text{CAPTURE} \rightarrow \text{VALIDATE} \rightarrow \text{NORMALIZE} \rightarrow \text{UNIFY} \rightarrow \text{CALCULATE} \rightarrow \text{CONTEXTUALIZE} \rightarrow \text{EVIDENCE} \rightarrow \text{SUMMARIZE} \rightarrow \text{HUMAN REVIEW} \rightarrow \text{APPROVED WORKFLOW} \rightarrow \text{AUDIT}$$

```
[ WhatsApp Client ]
        │ (Voice note, Meal Photo, or Text)
        ▼ HTTPS POST
[ Meta WhatsApp Cloud API ]
        │
        │ X-Hub-Signature-256 (HMAC-SHA256 over raw body)
        ▼
[ FastAPI Webhook: /api/v2/webhooks/whatsapp ]
        │ 1. Cryptographic HMAC verification (constant-time)
        │ 2. Receipt Deduplication (PostgreSQL webhook_receipts)
        │ 3. Atomic Outbox Enqueue (domain_event_outbox: "whatsapp.message.received")
        ▼ Fast HTTP 202 Accepted (<50ms)
[ Transactional Outbox Database ]
        │
        │ Leased by OutboxWorker (--poll or --once)
        ▼
[ OutboxWorker & WhatsAppIntakeHandler ]
        │
        ├── Step 1: Tenant & Patient Identity Resolution (public.resolve_channel_tenant)
        ├── Step 2: Media Retrieval Boundary (WhatsAppChannelSender.download_media)
        ├── Step 3: MediaVault Encrypted Staging (AES-256-GCM, tenant/patient AAD, lease table)
        │
        ├── Step 4: Provider-Neutral Multimodal Signal Conversion:
        │     ├── Voice: SpeechToTextProvider (Sarvam Saaras v3 ASR)
        │     └── Image: ImageAnalysisProvider (Gemini 1.5 Flash Vision)
        │
        ├── Step 5: MediaVault Immediate Disposal in finally: block
        │
        ├── Step 6: Intent Firewall & Ambiguity Detection
        │
        ├── Step 7: Deterministic Processing (Regex, Nutrition Taxonomy):
        │     ├── Glucose: IngestGlucoseReading -> IngestGlucoseHandler -> GlucoseObservation (PENDING)
        │     └── Meal Draft: LogMealDraft -> LogMealDraftHandler -> MealObservation (PENDING)
        │           └─ Deterministic ICMR/NIN Carbs & GI Calculation (TAXONOMY ONLY; NEVER LLM)
        │
        ├── Step 8: Interactive Confirmation / Correction Loop via WhatsApp
        │
        ├── Step 9: Canonical Domain Event Publishing (with full source_metadata provenance)
        │
        └── Step 10: Immutable Audit Logging (AuditEvent with PHI-free channel provenance)
```

---

## 2. Strict Clinical Safety & Autonomy Boundaries

1. **Deterministic Calculations Precede AI Interpretation**:
   - Nutrition calculations (carbohydrate grams, glycemic index categories) are executed **strictly by the deterministic nutrition taxonomy** (`backend/infrastructure/parsing/nutrition_taxonomy.py`).
   - Vision models extract **only food item candidates** (e.g., `"2 roti"`, `"1 katori dal"`). The model **never estimates or outputs nutrient grams, calories, or glycemic values**.
2. **AI Is Assistive and Evidence-First**:
   - High-level AI models produce **unapproved drafts** (`AIReviewArtifact` in `GENERATED` state) for licensed physician review in Doctor P.L.A.T.E.
   - **Autonomous Clinical Decisions Prohibited**: AI must NOT diagnose autonomously, prescribe medication, titrate dosages, or modify clinician-authored medication plans.
3. **Observation Decoupling**:
   - Glucose readings are **never derived from food images or meal descriptions**. A food photo produces a `MealObservation`, never a `GlucoseObservation`.
4. **Information Asymmetry Protection**:
   - Patient WhatsApp prompts ask for confirmation and portion adjustment (Small, Medium, Large) in plain Hinglish.
   - Clinician-facing metrics (carbohydrate grams, glycemic load, GI tier) are **withheld from the patient WhatsApp interface** to prevent anxiety or self-titration.

---

## 3. Runtime Roles & Scope

The system strictly enforces **exactly 3 runtime roles**:
- `PATIENT`: Records telemetry, receives confirmation prompts, views personal care tasks.
- `CAREGIVER`: Managed through verified caregiver delegation relationships with capability scoping.
- `DOCTOR`: Reviews telemetry, approves/edits/rejects AI review drafts, authors medication plans.

*Admin Web is completely removed from the current product scope.* Deprecated runtime roles (`ADMIN`, `DIETITIAN`, `FHW`, `COORDINATOR`) are prohibited at runtime.

---

## 4. Voice Intake Pipeline

```
[Inbound Voice Note] 
  → MIME & Size Validation (audio/*, <= 15MB)
  → Encrypted Storage in MediaVault (AES-256-GCM)
  → SarvamSpeechToTextProvider (Saaras v3)
  → Hinglish Transcript
  → Deterministic Intake Parser
  → Canonical IngestGlucoseReading or LogMealDraft
  → MediaVault Cleanup (finally block)
```

- **Supported Formats**: `audio/ogg`, `audio/mpeg`, `audio/mp4`, `audio/wav`, `audio/amr`.
- **Size Limit**: 15,000,000 bytes (15 MB).
- **Fallback**: Empty transcript or provider timeout safely falls back to `LOW_CONFIDENCE_GUIDANCE`:
  > *"Main photo ya audio mein khana sahi se pehchan nahi paya. Kripya thoda clear photo bhejein ya khane ka naam likh kar bhejein (jaise: '2 roti dal'). Aapki sahi health record ke liye confirm hona zaroori hai."*

---

## 5. Image Intake Pipeline

```
[Inbound Meal Photo]
  → MIME & Size Validation (image/jpeg, image/png, image/webp, <= 10MB)
  → Encrypted Storage in MediaVault (AES-256-GCM)
  → GeminiImageAnalysisProvider (Gemini 1.5 Flash)
  → FoodItemCandidate extraction (name + portion)
  → Plate Description Generation
  → Deterministic Nutrition Taxonomy Matching (ICMR-NIN)
  → LogMealDraft (Pending Confirmation)
  → Interactive Confirmation Reply to WhatsApp
  → MediaVault Cleanup (finally block)
```

- **Supported Formats**: `image/jpeg`, `image/png`, `image/webp`.
- **Size Limit**: 10,000,000 bytes (10 MB).
- **Safety Gate**: Low-confidence or unidentifiable meals set `unidentifiable=True` and emit `LOW_CONFIDENCE_GUIDANCE` without persisting speculative meals.

---

## 6. MediaVault Temporary Storage & Encryption Model

- **Zero Plaintext at Rest**: Media payloads are encrypted with **AES-256-GCM** using an ephemeral random 96-bit nonce per object.
- **AAD Cryptographic Binding**: The unique storage key `media/v1/{tenant_id}/{patient_id}/{media_type}/{message_id}-{timestamp}.bin` is bound as Additional Authenticated Data (AAD). Objects cannot be swapped across tenants or patients.
- **Lease Lifecycle**: Every write enters an in-memory lease table with an absolute retention TTL (default: 86,400s; dev: configurable).
- **Deterministic Cleanup**: Disposed immediately in the intake handler's `finally:` block. Background worker sweeps expired leases periodically.

---

## 7. Canonical Event & Provenance Propagation

Multimodal metadata is preserved without leaking PHI:

| Field | Source | Event / Entity | Description |
| :--- | :--- | :--- | :--- |
| `patient_id` | Resolver | All Entities & Events | UUID of the resolved active patient |
| `occurred_at` | Stated Time / Wall Clock | Observations | Preserved from explicit user time (e.g. "at 8:30 am"); never replaced with receipt time |
| `recorded_at` | Clock | Observations | Timestamp of system ingestion |
| `source_type` | Ingestion | `source_metadata` | `"voice"`, `"image"`, or `"text"` |
| `transcript_provider` | STT Provider | `source_metadata` | Provider name (e.g. `"sarvam"`) |
| `transcript_model` | STT Provider | `source_metadata` | Model identifier (e.g. `"saaras:v3"`) |
| `image_analysis_provider` | Vision Provider | `source_metadata` | Vision provider (e.g. `"gemini"`) |
| `image_confidence` | Vision Provider | `source_metadata` | `"high"`, `"medium"`, or `"low"` |
| `confirmation` | User Action | `MealObservation` | `PENDING` $\rightarrow$ `CONFIRMED` / `CORRECTED` / `REJECTED` |

---

## 8. Observability & PHI Guardrails

Metrics are exposed on `GET /metrics` in Prometheus format:
- Counters: `sarvam_requests_total`, `sarvam_stt_success_total`, `voice_pipeline_success_total`, `image_pipeline_success_total`, etc.
- Histograms: `sarvam_request_latency_seconds`.
- **PHI Blocklist**: `FORBIDDEN_LABEL_KEYS` strictly prevents `patient_id`, `phone`, `glucose`, `carbs`, `message`, or raw payloads from reaching Prometheus labels.
