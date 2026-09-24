# GATE 00 — EXISTING CODEBASE RECONNAISSANCE
## THALI × P.L.A.T.E. MIGRATION PROGRAM
**System Audit & Technical Baseline Assessment**

---

## 1. Executive Summary

### 1.1 Scope & Context
This audit establishes an evidence-based technical baseline of the current codebase in `/Users/subhamdas/Documents/health-a-thon-BioCypher--master`. The repository currently implements **Aahaar**, a prototype clinical telemetry engine originally developed for Health-a-thon 2026 (Diabetes Care Track). 

The organization is preparing a architectural migration toward the **THALI × P.L.A.T.E. Target Architecture**:
* **THALI**: Universal, role-aware mobile application serving Patients and Caregivers.
* **P.L.A.T.E.**: Care-team experience serving Doctors, Nurses, Care Coordinators, Dietitians, and Field Health Workers.
* **Unified Core**: A single shared backend, single identity model, unified patient record, canonical event model, single audit trail, and shared WhatsApp channel.

This reconnaissance document evaluates the existing code without altering any source code, configuration, or database structures.

### 1.2 Architectural State Assessment
* **Core Strengths**:
  1. **Strict Clinical Non-Diagnostic Boundaries**: Business logic rigorously enforces an assistive, descriptive voice; predictive risk scoring, diagnostic labeling, and pharmacological dosage directives are barred at code and test levels.
  2. **Information Asymmetry Engine**: Raw carbohydrate counts (g), Glycemic Index (GI) ratings, and Glycemic Volatility Indexes are sequestered strictly to doctor-facing views. The patient is exposed solely to calibrated household volumetric measures (**Small 150 ml**, **Medium 220 ml**, **Large 350 ml** *katori* bowls).
  3. **Verified Confirm Loop**: Meal proposals require explicit patient validation (`YES` or `correct l`) before transitioning to `confirmed` status; only confirmed meals populate clinical metrics.
  4. **Store-First Inbound Durability**: Raw patient speech is persisted in `raw_inbound` with unique Meta message IDs prior to downstream routing, preventing message loss and double-processing.
  5. **High-Resolution Reporting Pipeline**: A deterministic ReportLab Platypus engine paired with headless Matplotlib renders publication-grade two-page A4 PDF clinical summaries alongside an in-browser HTML/CSS mirror.
  6. **Comprehensive Safety Tests**: A 57-test suite protects clinical invariants, regex parsers, and access controls with 100% pass rate.

* **Critical Gaps Relative to Target Architecture**:
  1. **Zero Mobile Application Layer**: The existing client layer consists solely of a lightweight vanilla JS/HTML dashboard (`app/static/`). There is no mobile application, no Flutter/React Native codebase, and no offline-first mobile sync mechanism.
  2. **Absent Multi-Tenant Identity & RBAC**: Identity is coupled directly to phone numbers. There are no user accounts, no JWT/session tokens, no password hashes, and no clinical staff records (Doctor, Nurse, Dietitian, Care Coordinator, and Field Worker roles are completely unrepresented).
  3. **Insecure Administration Gate**: The clinic administration endpoints rely on a single shared symmetric header string (`AAHAAR_OP_KEY`, default `"aahaar-2026"`). All clinical read routes (`GET /api/v1/patients/*`) have zero authentication.
  4. **Unsigned Webhooks**: The Meta WhatsApp Cloud API webhook verifies the initial GET challenge token but fails to validate the `X-Hub-Signature-256` HMAC-SHA256 signature on inbound POST events.
  5. **Autonomous AI State Mutation**: In [`app/core/ai_worker.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/ai_worker.py#L180-L278), the decoupled AI intake worker directly registers blood sugar readings and proposes meals into the clinical database without mandatory clinician sign-off.
  6. **Demo Mode Phone Re-Binding**: [`app/core/process.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/process.py#L65-L74) contains a prototype auto-bind rule that reassigns the single demo patient to any unknown inbound phone number if the clinic database has only one patient.

---

## 2. Verified Repository Tree

```
/Users/subhamdas/Documents/health-a-thon-BioCypher--master/
├── LICENSE                          # [KEEP] BSD-3-Clause Open Source License
├── README.md                        # [KEEP] Project documentation & architecture overview
├── pytest.ini                       # [KEEP] Pytest runner configuration
├── requirements.txt                 # [MODIFY] Dependency manifest (needs migration tooling, auth)
├── .gitignore                       # [KEEP] Git exclusion list
├── aahaar-demo.db                   # [REMOVE] Local SQLite instance (generated artifact)
├── aahaar-demo.db-shm               # [REMOVE] SQLite shared memory file
├── aahaar-demo.db-wal               # [REMOVE] SQLite Write-Ahead Log
│
├── app/                             # [MODIFY] Core application package
│   ├── __init__.py                  # [KEEP] Package marker
│   ├── config.py                    # [MODIFY] Application settings (needs identity, tenant keys)
│   │
│   ├── core/                        # [MERGE/MODIFY] Pure Python core business logic
│   │   ├── __init__.py              # [KEEP] Package marker
│   │   ├── ai.py                    # [MERGE] Core conversational NLP & Gemini REST integration
│   │   ├── ai_worker.py             # [MODIFY] Decoupled background poller (remove auto-state writes)
│   │   ├── datamodel.py             # [REPLACE] SQLite schema (migrate to SQLAlchemy/Alembic multi-tenant)
│   │   ├── escalation.py            # [KEEP] 21:00 caregiver-first operational nudge generator
│   │   ├── intake_ai.py             # [MERGE] Intake field extractor (consolidate with ai.py)
│   │   ├── metrics.py               # [KEEP] Descriptive analytics: TIR, slots, CVI, Pearson r
│   │   ├── nutrition.py             # [KEEP] Indian food taxonomy, GI buckets, calibrated katoris
│   │   ├── parse.py                 # [KEEP] Multi-modal normalizer, typo refiner, ambiguity guard
│   │   ├── process.py               # [MODIFY] Ingress routing (remove demo auto-bind hack)
│   │   ├── report.py                # [KEEP] Clinical context builder for PDF & dashboard
│   │   └── seed.py                  # [MOVE] Seeding logic to tests/fixtures or migrations
│   │
│   ├── report/                      # [KEEP/MOVE] Clinical report compilation
│   │   ├── __init__.py              # [KEEP] Package marker
│   │   ├── charts.py                # [KEEP] Matplotlib 270 DPI dual-panel chart renderer
│   │   ├── html_preview.py          # [KEEP] HTML/CSS report preview mirror
│   │   └── pdf.py                   # [KEEP] ReportLab Platypus 2-page A4 PDF builder
│   │
│   ├── server/                      # [MODIFY] FastAPI HTTP layer
│   │   ├── __init__.py              # [KEEP] Package marker
│   │   ├── main.py                  # [MODIFY] Route definitions (add RBAC, JWT, tenant filtering)
│   │   └── whatsapp.py              # [MODIFY] Meta Cloud & Simulator backend (add HMAC signature verification)
│   │
│   └── static/                      # [REPLACE] Prototype single-page dashboard
│       ├── app.js                   # [REPLACE] Vanilla JS dashboard logic
│       ├── index.html               # [REPLACE] Semantic HTML5 dashboard layout
│       └── style.css                # [REPLACE] CSS styling rules
│
├── docs/                            # [KEEP] Documentation
│   └── WHATSAPP_DEMO.md             # [KEEP] Meta Cloud API & Cloudflare tunnel walkthrough
│
├── scripts/                         # [MODIFY] Operational & batch scripts
│   ├── analyze_stored.py            # [MODIFY] Offline Gemini batch analyzer
│   ├── demo.py                      # [MOVE] 14-day synthetic simulation generator (move to tests/e2e)
│   └── seed_real.py                 # [REMOVE] Prototype single-number seeder
│
└── tests/                           # [MODIFY] Test suite
    ├── conftest.py                  # [MODIFY] Test fixtures (add auth & tenant fixtures)
    ├── test_linking.py              # [MODIFY] Operator linking & diagnostic endpoint tests
    └── test_pipeline.py             # [KEEP] Clinical safety invariants, confirm loop, & metrics tests
```

---

## 3. Technology Inventory

| Technology Domain | Specified Component | Version / Specification | Actual File Reference | Implementation & Architectural Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Language Runtime** | Python | `>= 3.10` (runs in 3.14) | [`requirements.txt`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/requirements.txt#L1-L8) | Heavy use of native `dataclasses`, `from __future__ import annotations`, match syntax, typing unions (`tuple[int, ...]`). |
| **API Framework** | FastAPI | `>= 0.115` | [`app/server/main.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/main.py#L18) | ASGI application instance initialized via `create_app()`, utilizing `BackgroundTasks` for asynchronous worker dispatch. |
| **ASGI Server** | Uvicorn | `[standard]>= 0.30` | [`requirements.txt`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/requirements.txt#L2) | Production entry point for FastAPI serving HTTP on port 8000. |
| **Validation / DTO** | Pydantic | `>= 2.7` | [`requirements.txt`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/requirements.txt#L3) | Present in dependencies, though core models rely extensively on standard library `@dataclass`. |
| **Database Engine** | SQLite3 | Native C-Extension | [`app/core/datamodel.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/datamodel.py#L22) | Embedded serverless database. Configured with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and `PRAGMA busy_timeout=5000`. |
| **ORM / Data Access** | Native Python `sqlite3` | Raw SQL / No ORM | [`app/core/datamodel.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/datamodel.py#L88-L120) | Custom `Store` class wrapping raw connection, context manager transactions (`tx()`), and parameter substitution tuples. |
| **Analytics Engine** | NumPy & Python `statistics` | Native / Standard | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L9-L10) | Computes population standard deviation, Pearson correlation ($r$), and Time in Range over non-contiguous time series. |
| **Visualization** | Matplotlib | `>= 3.8` | [`app/report/charts.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/report/charts.py#L15-L18) | Configured with `matplotlib.use("Agg")` for headless execution. Generates 270 DPI PNG charts with shaded target corridors. |
| **PDF Generation** | ReportLab | `>= 4.0` | [`app/report/pdf.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/report/pdf.py#L14-L25) | Uses Platypus framework (`BaseDocTemplate`, `PageTemplate`, `Frame`, `Table`, `Paragraph`). Custom TrueType font registration (`DejaVuSans`). |
| **PDF Verification** | PyMuPDF (fitz) | `>= 1.24` | [`requirements.txt`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/requirements.txt#L8) | Included in environment for structural inspection and regression verification of rendered PDF documents. |
| **HTTP Client** | HTTPX & `urllib.request` | `>= 0.27` | [`app/core/ai.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/ai.py#L89), [`app/server/whatsapp.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/whatsapp.py#L17) | HTTPX handles REST integration with Google Gemini endpoints; `urllib.request` handles Meta WhatsApp Graph API requests. |
| **AI Integration** | Google Gemini REST API | `v1beta` | [`app/core/ai.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/ai.py#L70-L116) | Direct REST queries to `generativelanguage.googleapis.com`. Models: `gemini-3.8-flash`, `gemini-3.5-flash`, `gemini-3.1-flash-lite`. Dynamic discovery via `/v1beta/models`. |
| **Messaging Channel**| Meta WhatsApp Cloud API | Graph API `v21.0` | [`app/server/whatsapp.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/whatsapp.py#L25) | Integrated via `CloudBackend` (`POST /{phone_id}/messages` and `POST /{waba_id}/subscribed_apps`). Fallback: `SimulatorBackend`. |
| **Frontend UI** | Vanilla JS / CSS3 / HTML5 | Zero-Build | [`app/static/index.html`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/static/index.html) | Native browser technologies. No package manager, node runtime, or bundler. Uses native Fetch API and CSS variables. |
| **Testing Engine** | Pytest | `>= 8.0` | [`pytest.ini`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/pytest.ini) | 57 automated tests covering safety invariants, confirm loop, metrics, and role gates. |

---

## 4. Dependency & Coupling Analysis

### 4.1 Ingestion & Processing Flow
```
Meta Webhook / Inbound HTTP (POST /api/v1/webhooks/whatsapp)
    │
    ▼
app.server.main.webhook_inbound()
    │
    ├─► app.core.datamodel.Store.record_raw_received()  [DB Store-First Durability]
    │
    └─► fastapi.BackgroundTasks._process_unit()
             │
             ▼
        app.core.process.IngestService.handle()
             │
             ├─► app.core.datamodel.Store.get_patient_by_phone()
             ├─► app.core.datamodel.Store.active_window_for()
             │
             ├─► app.core.parse.parse_inbound()
             │        │
             │        ├─► app.core.ai.refine_text_local() [Typo / Phonetic Normalization]
             │        └─► app.core.nutrition.classify_text() [Indian Food Matching]
             │
             ├─► app.core.datamodel.Store.add_reading() OR propose_meal()
             │
             └─► app.server.whatsapp.CloudBackend.send_bulk()
                      │
                      ▼
                 Meta Graph API v21.0 (/messages)
```

### 4.2 Decoupled AI Intake Flow
```
Asynchronous Poller (app.core.ai_worker.IntakeWorker) OR API Trigger (POST /api/v1/analyze/stored)
    │
    ▼
app.core.datamodel.Store.raw_inbound_all()  [Read unrefined stored rows]
    │
    ▼
app.core.intake_ai.analyze_intake()
    │
    ├─► app.core.intake_ai._call_gemini_intake()  [Direct REST to Google Gemini]
    │         │
    │         └─► app.core.ai.discover_models()
    │
    └─► app.core.intake_ai._local_notifier()  [Deterministic Fallback]
             │
             ▼
        IntakeResult Synthesized
             │
             ├─► app.core.ai_worker.IntakeWorker._save_refined() [Update raw_inbound.refined_json]
             ├─► app.core.ai_worker.IntakeWorker._maybe_register() [Auto-write readings table]
             ├─► app.core.ai_worker.IntakeWorker._maybe_register_meal() [Auto-write meals table]
             │
             └─► app.server.whatsapp.CloudBackend.send() [Paced WhatsApp Follow-up]
```

### 4.3 Reporting & Visualization Flow
```
Client Request (POST /api/v1/patients/{pid}/report/build)
    │
    ▼
app.server.main.build_report()
    │
    ├─► app.core.report.latest_report_context()
    │        │
    │        ├─► app.core.metrics.compute_window_metrics()
    │        │        │
    │        │        ├─► app.core.datamodel.Store.meals_for_window(confirmed_only=True)
    │        │        └─► app.core.datamodel.Store.readings_for_window()
    │        │
    │        └─► app.core.report._patterns() [Observed pattern synthesis]
    │
    ├─► app.report.charts.render()
    │        │
    │        ├─► render_top() -> chart-top-{pid}.png (Corridor & Slots)
    │        └─► render_bottom() -> chart-bottom-{pid}.png (High-GI & PPBG Trend)
    │
    ├─► app.report.pdf.render() -> Aahaar-Doctor-Report-{pid}-{start}.pdf (Platypus 2-Page A4)
    │
    └─► app.report.html_preview.render_html() [In-Browser DOM Mirror]
```

### 4.4 Circular Dependencies & Coupling Hazards
* **Dynamic Inline Imports**: To prevent circular references, modules frequently perform function-level imports:
  - [`app/core/parse.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/parse.py#L126): `from .ai import refine_text_local` inside `parse_inbound()`.
  - [`app/core/parse.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/parse.py#L262): `from .nutrition import estimate_carbs_g, classify_text` inside `_items()`.
  - [`app/core/process.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/process.py#L102): `from .ai import analyze_patient_input` inside `handle()`.
  - [`app/core/ai_worker.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/ai_worker.py#L83): `from ..core.process import Outbound` inside `run_once()`.
* **Coupling Assessment**: While circular import crashes are avoided at runtime through deferred imports, this indicates tight structural coupling between parsing, AI interpretation, and business workflow processing.

---

## 5. Module-by-Module Technical Analysis

### 5.1 `app/config.py`
* **Purpose**: Central immutable configuration store using Python `@dataclass(frozen=True)`.
* **Exports**: `Settings`, `get_settings()`.
* **Key Configuration Defaults**:
  - `glucose_low`: `70.0 mg/dL`, `glucose_high`: `180.0 mg/dL` (Target TIR range).
  - `katori_ml`: `(150.0, 220.0, 350.0)` corresponding to Small, Medium, and Large katoris.
  - `whatsapp`: Channels `"simulator"` (default) or `"cloud"`.
  - `operator_key`: Secret string guarding administrative endpoints (default: `"aahaar-2026"`).
  - `ai_on_inbound`: Boolean switch (`False` by default) enforcing zero LLM calls on synchronous webhook.
  - `ai_intake`: Boolean switch (`False` by default) for the background worker thread.
  - `esc_hour`: `21` (9:00 PM operational nudge).
* **Defects / Risks**: Stores the administrative secret `operator_key` as a shared plaintext environment variable without salt, hashing, or rotation.

### 5.2 `app/core/datamodel.py`
* **Purpose**: Database persistence layer managing SQLite connection pooling and schema initialization.
* **Exports**: `Store`, `SCHEMA`, `iso()`, `parse_ts()`.
* **Key Mechanisms**:
  - Sets `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`.
  - Implements transaction context manager `tx()` with auto-commit and rollback.
  - Enforces single-caregiver constraint by executing `UPDATE caregivers SET active=0 WHERE patient_id=?` prior to inserting a new caregiver.
  - Implements deduplication in `record_raw_received()` via the `message_id` column.
* **Defects / Risks**: Raw SQL string concatenation in dynamic filtering queries; lacks database migration framework (Alembic); schema assumes a single clinic and lacks foreign keys for facilities, organizations, clinicians, or multi-tenant user accounts.

### 5.3 `app/core/nutrition.py`
* **Purpose**: Curated Indian food nutritional taxonomy, colloquial synonym aliases, and volumetric carb calculations.
* **Exports**: `FOODS`, `_ALIASES`, `classify_text()`, `detect_photo()`, `estimate_carbs_g()`, `gi_bucket_index()`, `KATORI_LABELS`.
* **Data Content**:
  - 35 standard Indian staple foods (`white rice`, `roti`, `dal`, `biryani`, `mixed sabzi`, `paneer curries`, etc.) mapped to genus, carbohydrates per 100g, GI bucket (`low`, `med`, `high`), and default portion (`m`).
  - Extensive colloquial dictionary (`chawal`, `bhat`, `chapati`, `phulka`, `parantha`, `aloo gobi`, `sambar`, `machhi`, `dahi`, `mithai`).
  - Fallback logic: Detects verb clues (`"khaya"`, `"ate"`, `"lunch"`) to generate a `"Mixed meal"` row ($16.0\text{g carbs/100g}$, medium GI) so uncatalogued meals are never rejected.
* **Mathematical Formula**:
  $$\text{carbs\_g} = \text{round}\left(\text{carbs\_per\_100g} \times \text{portion\_ml} \times 0.009,\, 1\right)$$

### 5.4 `app/core/parse.py`
* **Purpose**: Inbound message normalizer parsing glucose readings, food items, confirmations, and corrections.
* **Exports**: `ParsedInput`, `parse_inbound()`, `ambiguous_reading_values()`, `describe_items()`, `READING_TAG_LABELS`.
* **Key Logic**:
  - Extracts numeric blood glucose readings across explicit regexes (`"fasting 126"`, `"ppbg: 180"`, `"140 mg/dl"`) and natural language patterns (`"aaj subah fasting 135 tha"`). Valid range checked: $20.0 \le \text{glucose} \le 600.0\text{ mg/dL}$.
  - Identifies context tags: `fasting`, `pre`, `postprandial`, `postbreakfast`, `postlunch`, `postdinner`.
  - Normalizes colloquial affirmations (`yes`, `haan`, `theek hai`, `sahi hai`, `achha`, `ji haan`) into `kind="confirm"`.
  - Detects ambiguous multi-value readings via `ambiguous_reading_values()` (e.g. `"230 or 330"`).

### 5.5 `app/core/process.py`
* **Purpose**: Primary ingress pipeline service orchestrating role verification, active windows, and the confirm loop.
* **Exports**: `IngestService`, `Outbound`.
* **Key Logic**:
  - Resolves incoming phone number against patient and caregiver records.
  - **Prototype Hack Identified**: Lines 65–73: If the database contains exactly one patient with the default demo phone (`...9876501234`), the system dynamically rebinds that patient profile to the incoming phone number.
  - Enforces active logging window check; rejects logging outside window intervals.
  - In confirm loop: proposing a meal issues a quick-reply prompt showing only volumetric units (`"Detected: roti, dal · Medium (220 ml). Reply YES, or 'correct m/s/l'"`).
* **Defects / Risks**: The auto-bind rule on lines 65–73 represents a major multi-tenant hazard if deployed beyond a single-person hackathon demo.

### 5.6 `app/core/metrics.py`
* **Purpose**: Statistical calculation of clinical glycemic and dietary metrics over confirmed window data.
* **Exports**: `compute_window_metrics()`, `latest_metrics()`, `_pearson()`.
* **Analytics Produced**: Time-in-Range (TIR), Adherence Index, Mean Fasting Plasma Glucose (FPG), Mean Postprandial Glucose (PPBG), Post-Breakfast (PB), Post-Lunch (PL), Post-Dinner (PD), Weekday vs Weekend splits, Carb Volatility Index (CVI), and Pearson correlation ($r$).

### 5.7 `app/core/report.py`
* **Purpose**: Prepares structured descriptive data context for the clinical report.
* **Exports**: `build_report_context()`, `latest_report_context()`.
* **Key Logic**:
  - Assembles demographic summaries, metric cards, series arrays, and top 3 staple genera proportions.
  - Synthesizes `patterns`: Generates human-readable clinical observations (e.g., *"Mean postprandial glucose was 42.0 mg/dL higher on weekends than on weekdays"* or *"Meals containing items on the doctor's avoid list were logged 3 times"*).
  - Enforces non-diagnostic phrasing; censors clinical directives.

### 5.8 `app/core/escalation.py`
* **Purpose**: Operational 9:00 PM nudge engine checking for missing daily telemetry.
* **Exports**: `due_escalations()`.
* **Key Logic**:
  - Checks if current local hour $\ge 21$.
  - Iterates open active windows. Verifies if both a meal and reading have been logged for today's date.
  - If missing, checks idempotency key `esc-{window_id}-{YYYY-MM-DD}` in `outbound`.
  - Targets the active caregiver's phone first; falls back to the patient.
  - Issues non-clinical operational reminder: *"Just a quick check: today's meal photo and reading hasn't come in yet..."*

### 5.9 `app/core/seed.py`
* **Purpose**: Seeds demo patient, window, and clinical avoid items.
* **Exports**: `seed_demo()`.
* **Seed Data**: Patient "Sunita Devi" (`UHID: AH-2026-0042`), Caregiver "Anil Kumar (son)", Avoid list: `["soft drink", "gulab jamun", "sweet juice"]`. Default phone: `+917439030190`.

### 5.10 `app/core/ai.py`
* **Purpose**: Conversational AI refiner and Google Gemini REST API integration.
* **Exports**: `AIRefinement`, `discover_models()`, `test_gemini_api()`, `call_llm_reasoning()`, `refine_text_local()`, `analyze_patient_input()`, `get_last_ai_status()`.
* **Key Mechanisms**:
  - Regex typo map correcting common OCR/keyboard misspellings (`fstng` &rarr; `fasting`, `sugr` &rarr; `sugar`, `14o` &rarr; `140`).
  - Dynamic Gemini model discovery via HTTP GET `/v1beta/models?key=...`.
  - Gated live execution: Rejects Gemini API calls during live inbound requests unless `AAHAAR_AI_ON_INBOUND` is set to `True`.

### 5.11 `app/core/intake_ai.py`
* **Purpose**: Specialized AI intake collection assistant detecting missing logging details.
* **Exports**: `IntakeResult`, `analyze_intake()`.
* **Key Mechanisms**:
  - System prompt: Instructs LLM that it is an intake collection assistant, NOT a doctor. Explicitly forbids medical advice, targets, diagnoses, or prescriptions.
  - Identifies missing fields among: `reading_value`, `reading_tag`, `meal_items`, `portion`.
  - Produces Hinglish follow-up prompts limited to 70 characters.
  - Local deterministic fallback (`_local_notifier`) guarantees zero failure if Gemini API is unreachable.

### 5.12 `app/core/ai_worker.py`
* **Purpose**: Decoupled background poller daemon and on-demand stored message analyzer.
* **Exports**: `IntakeWorker`.
* **Key Logic**:
  - Background daemon thread running every 15 seconds (configurable via `AAHAAR_AI_INTAKE_INTERVAL`).
  - Reads unrefined rows from `raw_inbound`, invokes `analyze_intake()`, and saves result into `refined_json`.
  - **High-Risk Autonomous Writes**:
    - Lines 180–224: `_maybe_register()` automatically inserts a blood sugar reading into `readings` if `res.reading_status == "resolved"`.
    - Lines 225–279: `_maybe_register_meal()` automatically creates a pending meal proposal in `meals`.
  - Dispatches follow-up WhatsApp messages via `backend.send` if `should_send` is enabled, applying pacing delay (`AAHAAR_AI_INTAKE_SEND_GAP`).

### 5.13 `app/report/charts.py`
* **Purpose**: Headless Matplotlib visualization compiler producing 270 DPI chart panels.
* **Exports**: `render()`, `render_top()`, `render_bottom()`.
* **Panels Generated**:
  - **Top Panel (`render_top`)**: Longitudinal daily blood glucose. Plots Post-Breakfast (amber circle), Post-Lunch (green square), Post-Dinner (crimson triangle), and Fasting FPG (teal diamond) against a shaded green target corridor ($70-180\text{ mg/dL}$).
  - **Bottom Panel (`render_bottom`)**: Dual-axis plot with daily High-GI Dietary Share (%) bars (left axis) and overall Postprandial Glucose trend line (right axis), with shaded weekend spans.

### 5.14 `app/report/pdf.py`
* **Purpose**: ReportLab Platypus 2-page publication-grade A4 PDF compiler.
* **Exports**: `render()`, `page1()`, `page2()`, `on_page()`.
* **Layout Specifications**:
  - Page 1: Clinical Telemetry & Behavioral Nutrition Report (Adherence Index badge, demographic info-strip, Fasting/PPBG cards, meal slot breakdown, TIR stacked bar, GI distribution, katori table, weekday/weekend segmentation table, observed patterns, and mandatory Assistive Decision-Support Notice).
  - Page 2: Longitudinal Telemetry & Glycemic Excursion Charts (embedded top and bottom PNG charts, metric summary strip, correlation summary strip with Pearson $r$, and clinical chart reading guide).
  - Canvas callback `on_page`: Draws teal demarcation rule and standardized footer: *"Aahaar · Health-a-thon 2026 · Diabetes Care · Assistive (non-diagnostic) · Page X of 2"*.

### 5.15 `app/report/html_preview.py`
* **Purpose**: Responsive HTML/CSS mirror of the ReportLab 2-page report for in-browser dashboard viewing.
* **Exports**: `render_html()`, `CSS`.
* **Implementation**: Employs CSS Grid (`grid-template-columns: 1fr 1.18fr 1fr`), custom flex distribution bars, and SVG chart embeds, maintaining exact textual and stylistic fidelity with the PDF output.

### 5.16 `app/server/main.py`
* **Purpose**: FastAPI application setup, middleware configuration, and REST route controllers.
* **Exports**: `create_app()`, `app`.
* **Key Controllers**: 26 endpoints covering health, ingestion, webhooks, patient management, report building, diagnostics, and AI analysis.
* **Defects / Risks**: Absence of route-level authentication on patient telemetry; reliance on `X-Aahaar-Key` string comparison.

### 5.17 `app/server/whatsapp.py`
* **Purpose**: Channel abstraction decoupling business logic from Meta WhatsApp Graph API.
* **Exports**: `_Base`, `SimulatorBackend`, `CloudBackend`.
* **Key Logic**:
  - `_Base.parse_webhook()`: Flattens Meta webhook JSON into neutral wire format (`sender_phone`, `message_id`, `kind`, `text`, `photo_path`).
  - `SimulatorBackend`: Mock channel logging outbound messages to `outbound` SQLite table and stdout.
  - `CloudBackend`: Real integration with Meta Graph API `v21.0`. Handles HTTP POST `/messages`, media downloads, and WABA webhook subscriptions.
* **Defects / Risks**: Omits HMAC-SHA256 signature verification on inbound webhook requests.

### 5.18 `app/static/` (`index.html`, `app.js`, `style.css`)
* **Purpose**: Single-page web dashboard for clinical operators.
* **Features**: Overview KPIs, TIR visualization, trend chart embeds, report PDF preview/download, live inbound WhatsApp feed, direct doctor-to-patient messaging, and Meta/Gemini diagnostics.
* **Implementation**: Vanilla JavaScript polling endpoints every 3000ms via `setInterval`.

### 5.19 `scripts/` (`demo.py`, `seed_real.py`, `analyze_stored.py`)
* **`demo.py`**: CLI simulator generating 14 days of realistic meal proposals, confirmations, and glucose pricks (weekday vs. weekend variations, festive excursions) to verify the pipeline end-to-end.
* **`seed_real.py`**: CLI utility resetting the database and binding the demo patient to a real phone number for live WhatsApp testing.
* **`analyze_stored.py`**: Batch processing CLI executing Google Gemini analysis over stored `raw_inbound` records.

---

## 6. Database Schema & Data Modeling Analysis

The SQLite database is initialized via the SQL script in [`app/core/datamodel.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/datamodel.py#L27-L75).

```sql
CREATE TABLE IF NOT EXISTS patients(
    id INTEGER PRIMARY KEY,
    name TEXT,
    uh_id TEXT UNIQUE,
    phone TEXT,
    lang TEXT DEFAULT 'sa',
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS caregivers(
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    phone TEXT,
    name TEXT,
    ts TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS avoid_items(
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    set_by TEXT,
    item TEXT,
    ts TEXT
);

CREATE TABLE IF NOT EXISTS windows(
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'open',
    caregiver_phone TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS meals(
    id INTEGER PRIMARY KEY,
    window_id INTEGER REFERENCES windows(id),
    ts TEXT,
    sender_phone TEXT,
    role TEXT,
    source TEXT,
    status TEXT DEFAULT 'pending',
    items_json TEXT,
    portion TEXT,
    portion_ml REAL,
    carbs REAL,
    gi TEXT,
    confidence REAL,
    correction_note TEXT
);

CREATE TABLE IF NOT EXISTS readings(
    id INTEGER PRIMARY KEY,
    window_id INTEGER REFERENCES windows(id),
    ts TEXT,
    sender_phone TEXT,
    role TEXT,
    tag TEXT,
    value REAL
);

CREATE TABLE IF NOT EXISTS outbound(
    id INTEGER PRIMARY KEY,
    window_id INTEGER REFERENCES windows(id),
    ts TEXT,
    route TEXT,
    kind TEXT,
    body TEXT,
    unique_key TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS audit(
    id INTEGER PRIMARY KEY,
    ts TEXT,
    actor TEXT,
    action TEXT,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS raw_inbound(
    id INTEGER PRIMARY KEY,
    window_id INTEGER REFERENCES windows(id),
    ts TEXT,
    sender_phone TEXT,
    role TEXT,
    raw_text TEXT,
    refined_json TEXT,
    status TEXT,
    message_id TEXT
);

CREATE TABLE IF NOT EXISTS webhook_events(
    id INTEGER PRIMARY KEY,
    ts TEXT,
    event_type TEXT,
    client_ip TEXT,
    status TEXT,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS ix_meals_window ON meals(window_id);
CREATE INDEX IF NOT EXISTS ix_readings_window ON readings(window_id);
CREATE INDEX IF NOT EXISTS ix_raw_inbound_window ON raw_inbound(window_id);
CREATE INDEX IF NOT EXISTS ix_webhook_events_ts ON webhook_events(ts);
```

### 6.1 Schema Deficiencies Relative to Target Architecture
1. **Missing Identity Entities**: There are no tables for `users`, `credentials`, `sessions`, `roles`, or `permissions`. Neither clinicians nor patients have system accounts.
2. **Lack of Facility / Multi-Tenancy Segregation**: No `facilities`, `clinics`, `tenants`, or `departments` exist. Every table assumes a single shared clinical deployment.
3. **Absence of Care Team Structures**: Care team roles (Doctor, Nurse, Care Coordinator, Dietitian, Field Worker) cannot be modeled or assigned to patients.
4. **No Canonical Event Bus Architecture**: Telemetry is fragmented across `meals` and `readings`. There is no canonical `clinical_events` table unifying biometric readings, dietary ingestions, medication administrations, or symptoms under a single stream.
5. **Primitive Schema Migrations**: Relies on `CREATE TABLE IF NOT EXISTS` plus ad-hoc inline `ALTER TABLE` statements inside Python code rather than versioned, reversible migration scripts.

---

## 7. Identity & Authentication Analysis

### 7.1 Existing Identity Identification Mechanisms
* **Patient Identity**:
  - Identified in database by integer `id`, unique hospital identifier `uh_id`, and `phone`.
  - Inbound resolution: [`Store.get_patient_by_phone()`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/datamodel.py#L137-L153) strips non-digit characters (`re.sub(r"\D", "", phone)`) and matches on exact string or trailing 10 digits.
* **Caregiver Identity**:
  - Stored in `caregivers` table linked by `patient_id`.
  - Resolved dynamically: Matched against the active caregiver phone or `windows.caregiver_phone`.
* **Clinician / Administrative Identity**:
  - **Completely Absent**: There is no clinician entity, doctor table, or individual login mechanism.
  - The API checks for the presence of an HTTP header `X-Aahaar-Key` matching `settings.operator_key` (`"aahaar-2026"`).

### 7.2 Security Deficiencies
* **Spoofable Sender Verification**: On the simulator channel, any client can pass an arbitrary `sender_phone` string to spoof a patient or caregiver.
* **No Session Tokens / JWT**: The application does not issue, validate, or revoke cryptographic tokens.
* **No Multi-Factor Authentication**: Administrative actions (such as linking phone numbers or triggering outbound messages) require only the shared operator key.
* **PII Exposure**: Phone numbers, patient full names, and hospital identifiers are stored in unencrypted SQLite tables.

---

## 8. Role-Based Access Control (RBAC) & Authorization Analysis

### 8.1 Current Implementation State
Authorization is implemented as a binary phone-matching role guard inside [`app/core/process.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/process.py#L142-L160):

```python
def _role(self, patient: dict, window: dict, phone: Optional[str]) -> tuple[str, bool]:
    # Match patient phone -> ("patient", True)
    # Match caregiver phone -> ("caregiver", True)
    # Otherwise -> ("patient", False)
```

### 8.2 Authorization Boundaries Matrix

| Endpoint Route | HTTP Method | Guard Mechanism | Authorized Caller | Gaps / Vulnerabilities |
| :--- | :--- | :--- | :--- | :--- |
| `/healthz` | `GET` | None | Public | None (standard health check). |
| `/api/v1/inbound` | `POST` | None | Public / Simulator | Arbitrary sender spoofing possible. |
| `/api/v1/webhooks/whatsapp` | `GET` | Query Token (`hub.verify_token`) | Meta Graph Webhook | Validates challenge token; acceptable for setup. |
| `/api/v1/webhooks/whatsapp` | `POST` | None (Store-first) | Meta Graph Webhook | **CRITICAL**: No HMAC signature verification. |
| `/api/v1/patients` | `GET` | None | Public | **HIGH**: Unauthenticated disclosure of all patient PII. |
| `/api/v1/patients` | `POST` | `X-Aahaar-Key` Header | Operator Key Holder | Shared static secret; no individual audit. |
| `/api/v1/patients/{pid}/linked` | `POST` | `X-Aahaar-Key` Header | Operator Key Holder | Shared static secret; phone reassignment without OTP. |
| `/api/v1/patients/{pid}/message`| `POST` | `X-Aahaar-Key` Header | Operator Key Holder | Can send arbitrary WhatsApp text to patients. |
| `/api/v1/patients/{pid}/metrics`| `GET` | None | Public | **HIGH**: Unauthenticated access to patient glucose data. |
| `/api/v1/patients/{pid}/report` | `GET` | None | Public | **HIGH**: Unauthenticated access to full clinical report. |
| `/api/v1/patients/{pid}/report/build`| `POST` | None | Public | Allows arbitrary unauthenticated server CPU load. |
| `/api/v1/patients/{pid}/report/file` | `GET` | None | Public | **HIGH**: Unauthenticated download of patient medical PDF. |
| `/api/v1/patients/{pid}/log` | `GET` | None | Public | **HIGH**: Unauthenticated access to full patient WhatsApp history. |
| `/api/v1/patients/{pid}/clear-chat` | `POST` | None | Public | **CRITICAL**: Unauthenticated deletion of conversational records. |
| `/api/v1/inbound/live` | `GET` | None | Public | **HIGH**: Real-time broadcast of all incoming messages to anyone. |
| `/api/v1/analyze/stored` | `POST` | `X-Aahaar-Key` Header | Operator Key Holder | Shared static secret. |
| `/api/v1/debug/*` | `GET`/`POST` | None | Public | **HIGH**: Unauthenticated triggering of WhatsApp and Gemini pings. |

---

## 9. WhatsApp Channel Architecture Trace

```
Meta WhatsApp Cloud API Server
    │
    ▼ HTTPS POST
FastAPI Ingress Endpoint: app.server.main.webhook_inbound()
    │
    ├─► Step 1: Payload Inspection & Error Shielding
    │         Extracts entry[0].changes[0].value. If invalid JSON, returns HTTP 400.
    │
    ├─► Step 2: Channel Payload Flattening (app.server.whatsapp.CloudBackend.parse_webhook)
    │         Extracts wa_id, message_id, timestamp, text body, or image ID.
    │
    ├─► Step 3: Store-First Persistence (app.core.datamodel.Store.record_raw_received)
    │         Executes INSERT INTO raw_inbound. 
    │         Checks message_id uniqueness: if duplicate, flags unit['_duplicate'] = True.
    │
    ├─► Step 4: Webhook Event Telemetry (app.core.datamodel.Store.record_webhook_event)
    │         Persists timestamp, client IP, delivery status, and unit count to webhook_events.
    │
    ├─► Step 5: Immediate Webhook Return
    │         Returns HTTP 200 {"ok": True, "processed": N} to Meta within ~15ms.
    │
    └─► Step 6: Asynchronous Processing (FastAPI BackgroundTasks -> _process_unit)
              │
              ▼
         app.core.process.IngestService.handle()
              │
              ├─► Sender Identity Resolution:
              │     Queries Store.get_patient_by_phone(sender_phone).
              │     Matches exact phone or trailing 10 digits.
              │
              ├─► Window Verification:
              │     Queries Store.active_window_for(patient_id).
              │
              ├─► Role Guard Check:
              │     IngestService._role(patient, window, sender_phone).
              │     Validates whether sender is Patient or Caregiver.
              │
              ├─► Raw Processing Update:
              │     Store.mark_raw_processed(raw_id, window_id, role, status).
              │
              ├─► Ambiguity Pre-Check:
              │     parse.ambiguous_reading_values(raw_text).
              │     If ambiguous (e.g. "230 or 330"), suppresses meal proposal.
              │
              ├─► Input Normalization & Parsing (app.core.parse.parse_inbound):
              │     - Glucose Readings: Range check (20-600), context tag extraction.
              │     - Meal Plates: Text token matching, katori portion assignment.
              │     - Confirmations: Affirmation matching ("yes", "correct s").
              │
              ├─► Business Action Execution:
              │     - If Reading: Store.add_reading(); generates text reply.
              │     - If Meal: Store.propose_meal(status='pending'); generates quick-reply.
              │     - If Confirm: Store.finalize_meal(status='confirmed'); generates confirmation.
              │
              └─► Outbound WhatsApp Dispatch:
                    app.server.whatsapp.CloudBackend.send()
                    Executes HTTP POST to https://graph.facebook.com/v21.0/{phone_id}/messages
                    Records outbound reply in outbound table.
```

---

## 10. AI Architecture & Execution Trace

### 10.1 Models & API Endpoints
* **Provider**: Google Generative AI (Google Gemini REST API).
* **Base URL**: `https://generativelanguage.googleapis.com/v1beta`.
* **Target Models**: Dynamically discovered via `/v1beta/models?key=...`. Falls back to hardcoded precedence:
  1. `gemini-3.8-flash`
  2. `gemini-3.5-flash`
  3. `gemini-3.1-flash-lite`

### 10.2 AI Integration Modes

```
+--------------------------------------------------------------------------------------------------+
|                                        AI EXECUTION MODES                                        |
+------------------------------+----------------------------------+--------------------------------+
| Mode                         | Execution Path                   | Safety Gating & Behavior       |
+------------------------------+----------------------------------+--------------------------------+
| 1. Synchronous Inbound       | Webhook -> IngestService         | STRICTLY GATED OFF BY DEFAULT. |
|    (app/core/ai.py)          | -> analyze_patient_input()       | Enabled only if                |
|                              | -> call_llm_reasoning()          | AAHAAR_AI_ON_INBOUND=True.     |
|                              |                                  | Fallback: Local regex refiner. |
+------------------------------+----------------------------------+--------------------------------+
| 2. Decoupled Intake Worker   | Background IntakeWorker Daemon   | ASYNCHRONOUS POLLER.           |
|    (app/core/ai_worker.py)   | OR POST /api/v1/analyze/stored   | Reads stored raw_inbound.      |
|    (app/core/intake_ai.py)   | -> analyze_intake()              | Evaluates missing fields.      |
|                              | -> _call_gemini_intake()         | Generates Hinglish prompts.    |
+------------------------------+----------------------------------+--------------------------------+
| 3. Offline Batch CLI         | python -m scripts.analyze_stored | OFFLINE BATCH UTILITY.         |
|    (scripts/analyze_stored)  | -> analyze_patient_input()       | Runs over historical logs.     |
|                              |                                  | Writes refined_json to SQLite. |
+------------------------------+----------------------------------+--------------------------------+
```

### 10.3 Prompts & Output Schemas
1. **Clinical Reasoning Prompt ([`app/core/ai.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/ai.py#L180-L188))**:
   ```
   Clinical diabetes assistant. Patient: {patient_name}. Message: '{text}'.
   Analyze intent and return strictly valid JSON: 
   {"intent": "reading"|"meal"|"confirm"|"clarify", 
    "reading": number or null, 
    "reading_tag": "fasting"|"postbreakfast"|"postlunch"|"postdinner"|"pre"|"postprandial" or null, 
    "dishes": ["dish1", ...], 
    "conversational_reply": "short helpful reply in patient language"}
   ```
2. **Intake Collection Prompt ([`app/core/intake_ai.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/intake_ai.py#L98-L113))**:
   ```
   You are the intake collector assistant for a diabetes-logging system. You are NOT a doctor. 
   You never give medical advice, targets, diagnoses, doses, or diet prescriptions, and you never 
   comment on what a reading number means.
   Your only job: decide which logging fields the patient's latest message provided, and if 
   anything is missing or ambiguous, ask for EXACTLY ONE in a short friendly Hinglish question 
   (under 70 characters)...
   Return strictly valid JSON: {"intent":"reading"|"meal"|"confirm"|"clarify", 
   "missing":["reading_value"|"reading_tag"|"meal_items"|"portion"], "reply":"...", 
   "items":["dish 1",...], "portion":"s"|"m"|"l"}
   ```

### 10.4 Clinical State Mutation Finding
* **CRITICAL FINDING**: In [`app/core/ai_worker.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/ai_worker.py#L180-L278), AI analysis output can directly mutate clinical database state without clinician review:
  - Lines 215–218: If `res.reading_status == "resolved"` and `res.reading_value` is present, the worker invokes `store.add_reading()` to write an official blood glucose entry.
  - Lines 268–276: If `res.meal_items` are identified, the worker invokes `store.propose_meal()` to create a pending meal entry.
  - While reading deduplication checks exist, autonomous writes from generative AI outputs violate medical device safety standards.

---

## 11. Clinical Analytics Inventory

| Metric Name | Source Data | Formula / Calculation | Implementation File | Output Location | Patient Visible? | Clinician Visible? | Clinical Validation Status | Automated Test Coverage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Time-in-Range (TIR: In Range %)** | `readings.value` | $\frac{\sum [70 \le v \le 180]}{N_{\text{total}}} \times 100$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L144-L151) | Metrics JSON, Report PDF p.1, Dashboard Overview | **NO** | **YES** | Follows consensus clinical target range ($70-180\text{ mg/dL}$). | [`test_tir_classification_70_180`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/tests/test_pipeline.py#L114) |
| **TIR: Above Range %** | `readings.value` | $\frac{\sum [v > 180]}{N_{\text{total}}} \times 100$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L146) | Metrics JSON, Report PDF p.1, Dashboard Overview | **NO** | **YES** | Consensus hyperglycemia threshold ($>180\text{ mg/dL}$). | [`test_tir_classification_70_180`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/tests/test_pipeline.py#L114) |
| **TIR: Below Range %** | `readings.value` | $\frac{\sum [v < 70]}{N_{\text{total}}} \times 100$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L147) | Metrics JSON, Report PDF p.1, Dashboard Overview | **NO** | **YES** | Consensus hypoglycemia threshold ($<70\text{ mg/dL}$). | [`test_tir_classification_70_180`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/tests/test_pipeline.py#L114) |
| **Adherence Index** | `meals.ts`, `readings.ts`, `windows` | $\frac{\text{Active Logging Days}}{\text{Eligible Window Days}} \times 100$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L100-L102) | Metrics JSON, Report PDF p.1, Dashboard Overview | **NO** | **YES** | Operational behavioral logging compliance metric. | Covered via [`scripts/demo.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/scripts/demo.py#L145). |
| **Mean Fasting Plasma Glucose (FPG)** | `readings.value` (`tag='fasting'`) | $\frac{1}{N} \sum v_{\text{fasting}}$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L117) | Metrics JSON, Report PDF p.1 & p.2, Dashboard | **NO** | **YES** | Standard fasting blood glucose arithmetic mean. | Verified via report context tests. |
| **Mean Postprandial Glucose (PPBG)** | `readings.value` (`tag` in PP tags) | $\frac{1}{N} \sum v_{\text{post}}$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L131) | Metrics JSON, Report PDF p.1 & p.2, Dashboard | **NO** | **YES** | Aggregate postprandial blood glucose mean. | Verified via report context tests. |
| **Post-Breakfast PPBG Mean** | `readings.value` (`slot='postbreakfast'`) | $\frac{1}{N} \sum v_{\text{pb}}$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L138-L142) | Metrics JSON, Report PDF p.1 & p.2, Dashboard | **NO** | **YES** | Segmented post-breakfast glycemic response. | [`test_post_slot_stats_split_weekday_weekend`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/tests/test_pipeline.py#L176) |
| **Post-Lunch PPBG Mean** | `readings.value` (`slot='postlunch'`) | $\frac{1}{N} \sum v_{\text{pl}}$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L138-L142) | Metrics JSON, Report PDF p.1 & p.2, Dashboard | **NO** | **YES** | Segmented post-lunch glycemic response. | [`test_post_slot_stats_split_weekday_weekend`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/tests/test_pipeline.py#L176) |
| **Post-Dinner PPBG Mean** | `readings.value` (`slot='postdinner'`) | $\frac{1}{N} \sum v_{\text{pd}}$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L138-L142) | Metrics JSON, Report PDF p.1 & p.2, Dashboard | **NO** | **YES** | Segmented post-dinner glycemic response. | [`test_post_slot_stats_split_weekday_weekend`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/tests/test_pipeline.py#L176) |
| **Weekday vs Weekend PPBG Delta** | `readings.value` & day of week | $\mu_{\text{weekend\_ppbg}} - \mu_{\text{weekday\_ppbg}}$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L229) | Metrics JSON, Report PDF p.1, Dashboard Overview | **NO** | **YES** | Chronobiological lifestyle excursion delta. | [`test_weekday_weekend_ppbg_split`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/tests/test_pipeline.py#L125) |
| **High-GI Dietary Share (%)** | `meals.gi` (`status IN confirmed,corrected`) | $\frac{N_{\text{high\_gi\_meals}}}{N_{\text{total\_meals}}} \times 100$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L175) | Metrics JSON, Report PDF p.1 & p.2, Dashboard | **NO** | **YES** | Descriptive dietary intake proportion. | Verified via report context tests. |
| **Carb Volatility Index (CVI)** | `meals.carbs` grouped by day | $\frac{\sigma_{\text{daily\_carbs}}}{\mu_{\text{daily\_carbs}}}$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L170-L173) | Metrics JSON, Report PDF p.1, Dashboard Overview | **NO** | **YES** | Population coefficient of variation of daily carbs. | Verified via report context tests. |
| **High-GI vs PPBG Correlation ($r$)** | Daily high-GI share & daily mean PPBG | $\frac{\sum (x - \bar{x})(y - \bar{y})}{\sqrt{\sum (x - \bar{x})^2 \sum (y - \bar{y})^2}}$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L237-L249) | Metrics JSON, Report PDF p.2, Dashboard Trends | **NO** | **YES** | Pearson bivariate correlation coefficient. Requires $\ge 3$ pairs. | Covered in report context compilation. |
| **Doctor-Set Avoid List Hits** | `meals.items_json`, `avoid_items` | $\sum [\text{item} \in \text{avoid\_items}]$ | [`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py#L165-L167) | Metrics JSON, Report PDF p.1, Dashboard Overview | **NO** | **YES** | Reflective counting of doctor-proscribed foods. | Verified in report context tests. |

---

## 12. Reporting Architecture Analysis

```
                                      app/core/datamodel.py
                                                │
                                                ▼
                                      app/core/metrics.py
                                                │
                                                ▼
                                      app/core/report.py
                                   (build_report_context)
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       ▼                                                 ▼
             app/report/charts.py                             app/report/html_preview.py
              (Matplotlib Agg)                                   (Pure HTML5/CSS3)
                       │                                                 │
          ┌────────────┴────────────┐                                    │
          ▼                         ▼                                    │
    chart-top.png           chart-bottom.png                             │
   (Corridor Panel)        (Dietary Trend)                               │
          │                         │                                    │
          └────────────┬────────────┘                                    │
                       ▼                                                 ▼
               app/report/pdf.py                              FastAPI Dashboard Inject
            (ReportLab Platypus)                              (GET .../report/preview)
                       │                                                 │
                       ▼                                                 ▼
          Two-Page Lab-Style A4 PDF                          Responsive On-Screen View
       (Aahaar-Doctor-Report-*.pdf)                         (Interactive Web Workstation)
```

### 12.1 Evaluation as P.L.A.T.E. Evidence Layer Candidate
* **High Reusability**: The reporting core (`charts.py`, `pdf.py`, `html_preview.py`, `report.py`) is modular, headless, and independent of any web framework.
* **Clinical Language Rigor**: The reports adhere strictly to assistive, non-diagnostic standards with mandatory disclaimers and descriptive summaries.
* **Migration Strategy**: This subsystem can be extracted intact into the target P.L.A.T.E. evidence service with minor refactoring to pull data from a unified event store rather than direct SQLite queries.

---

## 13. Frontend Dashboard Analysis

### 13.1 Views & Component Inventory
The frontend located in [`app/static/`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/static/) implements a single-page interface:
1. **Sidebar / Patient Navigator**: Displays list of registered patients, UHID numbers, assigned caregivers, and active window tags. Includes `+ Add Patient` modal.
2. **Tab 1: Overview**: Renders KPI stat cards (Adherence, FPG, PPBG, TIR), stacked TIR distribution bar, meal-slot delta cards, readings context table, dietary summary, and clinical pattern cards.
3. **Tab 2: Trends**: Displays embedded 270 DPI Matplotlib charts (upper corridor panel and lower high-GI dietary share panel).
4. **Tab 3: Report**: Contains `Build doctor report` trigger, download link for compiled 2-page PDF, and responsive on-screen HTML preview.
5. **Tab 4: Messages**: Displays real-time conversational ledger between patient/caregiver and Aahaar. Includes live WhatsApp feed ticker.
6. **Tab 5: Live & Diagnostics**: Clinic-side phone linking form (`patient_phone`, `caregiver_phone`, `operator_key`), direct WhatsApp text composer, AI intake trigger, Meta WABA subscription button, and Gemini diagnostic test probes.
7. **Tab 6: Audit**: Chronological log of system, administrative, and clinical events.

### 13.2 Subsystem Maturity Classification
* **CLASSIFICATION: PROTOTYPE / DEMO**
* **Technical Deficiencies**:
  - Unauthenticated access: Anyone with network access to port 8000 can view all patient records, medical readings, and live chat transcripts.
  - Hardcoded polling: Relies on `setInterval(..., 3000)` creating continuous network overhead regardless of tab visibility.
  - Zero framework structure: Monolithic 646-line `app.js` file manipulating DOM directly via `innerHTML`.
  - Fragile error handling: Network exceptions display alert boxes or unstyled error divs.

---

## 14. Test Architecture & Coverage Inventory

The repository contains **57 automated tests** located across two test files in [`tests/`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/tests/). All 57 tests pass cleanly in 7.88s.

```
tests/test_linking.py   ................ (16 tests)
tests/test_pipeline.py  ......................................... (41 tests)
Total: 57 passed, 0 failures.
```

### 14.1 Detailed Test Inventory

| Test Function Name | File Reference | Invariant Protected | Test Level | External Service Dependencies | Target Architecture Survival Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `test_endpoint_requires_operator_key` | `test_linking.py:27` | Operator key required (403 if invalid). | Integration | None (Mocked) | **REPLACE** (Replace with RBAC/JWT test). |
| `test_endpoint_links_and_lists_numbers` | `test_linking.py:36` | Dynamic phone linking persistence. | Integration | None (Mocked) | **MODIFY** (Update for multi-tenant patient record). |
| `test_endpoint_rejects_garbage_phone` | `test_linking.py:50` | E.164 phone number validation. | Unit | None | **KEEP** (Preserve validation invariant). |
| `test_cloud_inbound_resolves_patient_by_sender_phone` | `test_linking.py:60` | Phone-to-patient identity resolution. | Integration | None (Mocked) | **MODIFY** (Migrate to unified identity model). |
| `test_cloud_inbound_fails_for_unlinked_number` | `test_linking.py:67` | Rejection of unauthorized senders. | Integration | None (Mocked) | **KEEP** (Critical security invariant). |
| `test_relink_phones_changes_allowed_senders` | `test_linking.py:75` | Caregiver phone binding replacement. | Integration | None (Mocked) | **KEEP** (Role guard invariant). |
| `test_reseed_keeps_operator_linked_numbers` | `test_linking.py:91` | Seed data idempotency. | Unit | None | **REMOVE** (Seed scripts to be phased out). |
| `test_meta_webhook_digits_only_matches_plus_phone` | `test_linking.py:101` | Meta digit-only phone normalization. | Unit | None | **KEEP** (WhatsApp ingestion invariant). |
| `test_patient_sends_fasting_keyword_only_gets_helpful_ai_prompt` | `test_linking.py:109` | Conversational clarifying prompt. | Integration | None (Local AI) | **KEEP** (THALI conversational invariant). |
| `test_patient_log_returns_inbound_and_outbound` | `test_linking.py:118` | Audit trail completeness. | Integration | None (Mocked) | **KEEP** (Unified audit invariant). |
| `test_meta_webhook_endpoint_background_processing` | `test_linking.py:130` | Fast webhook return & background task. | Integration | None (Mocked) | **KEEP** (Webhook performance invariant). |
| `test_debug_status_and_test_whatsapp` | `test_linking.py:166` | Diagnostic status reporting. | Integration | None (Mocked) | **MODIFY** (Update for production health checks). |
| `test_clear_patient_chat` | `test_linking.py:183` | Chat thread clearing logic. | Integration | None (Mocked) | **MODIFY** (Restrict to soft-delete/archive). |
| `test_debug_webhooks_endpoint` | `test_linking.py:210` | Webhook event telemetry logging. | Integration | None (Mocked) | **KEEP** (Observability invariant). |
| `test_debug_meta_subscribe` | `test_linking.py:232` | WABA webhook subscription handler. | Integration | None (Mocked) | **KEEP** (Channel configuration invariant). |
| `test_debug_test_gemini` | `test_linking.py:242` | Gemini test endpoint rejects missing key. | Integration | None (Mocked) | **KEEP** (AI configuration invariant). |
| `test_parse_reading_from_text` | `test_pipeline.py:38` | Regex parsing of blood glucose values. | Unit | None | **KEEP** (Core parser invariant). |
| `test_parse_out_of_range_reading_refused` | `test_pipeline.py:43` | Out-of-bounds glucose refusal ($>600$). | Unit | None | **KEEP** (Clinical boundary invariant). |
| `test_parse_confirm_portion` | `test_pipeline.py:48` | Katori portion confirmation parsing. | Unit | None | **KEEP** (THALI portion invariant). |
| `test_unregistered_number_refused` | `test_pipeline.py:54` | Rejection of unlinked telephone numbers. | Integration | None (Mocked) | **KEEP** (Role guard invariant). |
| `test_two_number_rule` | `test_pipeline.py:63` | Patient + 1 Caregiver maximum rule. | Integration | None (Mocked) | **KEEP** (Core role invariant). |
| `test_only_confirmed_meals_count` | `test_pipeline.py:83` | Confirm loop: pending meals excluded. | Integration | None (Mocked) | **KEEP** (Clinical safety invariant). |
| `test_portion_correction_applies` | `test_pipeline.py:97` | Portion correction updates state. | Integration | None (Mocked) | **KEEP** (Confirm loop invariant). |
| `test_reading_sanity_guard` | `test_pipeline.py:105` | Extreme values excluded from DB. | Integration | None (Mocked) | **KEEP** (Clinical safety invariant). |
| `test_tir_classification_70_180` | `test_pipeline.py:114` | TIR calculations ($70-180\text{ mg/dL}$). | Unit | None | **KEEP** (Clinical analytics invariant). |
| `test_weekday_weekend_ppbg_split` | `test_pipeline.py:125` | Chronobiological weekend segmentation. | Unit | None | **KEEP** (P.L.A.T.E. metric invariant). |
| `test_parse_meal_slot_readings_from_text` | `test_pipeline.py:148` | Slot tag parsing (PB, PL, PD). | Unit | None | **KEEP** (Core parser invariant). |
| `test_post_slot_inferred_from_preceding_meal` | `test_pipeline.py:160` | Preceding meal slot inference. | Integration | None (Mocked) | **KEEP** (Core analytics invariant). |
| `test_post_slot_stats_split_weekday_weekend`| `test_pipeline.py:176` | Meal slot statistics segmentation. | Unit | None | **KEEP** (P.L.A.T.E. metric invariant). |
| `test_chart_context_has_three_slot_series` | `test_pipeline.py:198` | Report chart context series generation. | Unit | None | **KEEP** (Reporting invariant). |
| `test_report_context_has_no_forbidden_language`| `test_pipeline.py:217` | Censors diagnostic/predictive words. | Unit | None | **KEEP** (CRITICAL clinical non-diagnostic invariant). |
| `test_patient_replies_never_mention_carbs_or_gi`| `test_pipeline.py:225` | Patient text hides carbs & GI values. | Unit | None | **KEEP** (CRITICAL information asymmetry invariant). |
| `test_escalation_idempotent_and_daily_cap` | `test_pipeline.py:235` | 21:00 nudge fires max once per day. | Integration | None (Mocked) | **KEEP** (Operational nudge invariant). |
| `test_natural_language_glucose_reading` | `test_pipeline.py:266` | Hinglish/conversational glucose parsing. | Unit | None | **KEEP** (THALI NLP invariant). |
| `test_natural_language_meal_and_confirm` | `test_pipeline.py:285` | Hinglish meal description parsing. | Unit | None | **KEEP** (THALI NLP invariant). |
| `test_typo_correction_and_talking_back_ai`| `test_pipeline.py:304` | Typo refiner (`14o` &rarr; `140`). | Integration | None (Local AI) | **KEEP** (THALI NLP invariant). |
| `test_all_raw_patient_text_is_logged_in_database`| `test_pipeline.py:319`| Raw speech audit completeness. | Integration | None (Mocked) | **KEEP** (Unified audit invariant). |
| `test_prick_keyword_parsing` | `test_pipeline.py:327` | Colloquial `"prick 142"` parsing. | Integration | None (Mocked) | **KEEP** (THALI NLP invariant). |
| `test_live_inbound_api_and_unlinked_visibility`| `test_pipeline.py:342`| Live inbound feed shows unlinked msgs. | Integration | None (Mocked) | **MODIFY** (Update for Admin Console API). |
| `test_audit_defenses_zero_readings_and_pending_matching`| `test_pipeline.py:362`| Chart render safety on empty data. | Unit | None | **KEEP** (Defensive graphics invariant). |
| `test_webhook_store_first_duplicate_skip` | `test_pipeline.py:406` | Store-first Meta message deduplication. | Integration | None (Mocked) | **KEEP** (Webhook idempotency invariant). |
| `test_llm_gated_off_live_path_by_default` | `test_pipeline.py:432` | LLM gated off live webhook path. | Unit | None | **KEEP** (Performance & reliability invariant). |
| `test_intake_local_notifier_asks_for_missing`| `test_pipeline.py:442`| Missing field intake collection. | Unit | None | **KEEP** (THALI intake invariant). |
| `test_intake_never_medical_advice` | `test_pipeline.py:462` | Intake prompt bars medical advice. | Unit | None | **KEEP** (Clinical safety invariant). |
| `test_intake_worker_picks_stored_rows_and_routes_reply`| `test_pipeline.py:474`| Asynchronous intake worker execution. | Integration | None (Mocked) | **MODIFY** (Update for event-driven worker). |
| `test_analyze_stored_endpoint_operator_keyed_and_send`| `test_pipeline.py:506`| Operator key required for analysis. | Integration | None (Mocked) | **REPLACE** (Replace with RBAC auth). |
| `test_live_inbound_auto_analyzes_and_pushes_followup_once`| `test_pipeline.py:541`| Auto-analysis on dashboard read. | Integration | None (Mocked) | **MODIFY** (Decouple read from background task). |
| `test_live_inbound_on_read_send_off_keeps_hints_only`| `test_pipeline.py:569`| Read-only analysis switch. | Integration | None (Mocked) | **KEEP** (Configuration invariant). |
| `test_ambiguous_reading_values` | `test_pipeline.py:587` | Ambiguity value detector ($230\text{ vs }330$). | Unit | None | **KEEP** (Clinical safety invariant). |
| `test_webhook_suppresses_meal_confirm_for_ambiguous_reading`| `test_pipeline.py:596`| Confirmation suppression on ambiguity. | Integration | None (Mocked) | **KEEP** (Clinical safety invariant). |
| `test_intake_worker_registers_resolved_reading_once`| `test_pipeline.py:612`| Worker reading auto-registration. | Integration | None (Mocked) | **MODIFY** (Add clinician approval requirement). |
| `test_intake_worker_never_registers_ambiguous_reading`| `test_pipeline.py:629`| Ambiguous readings never auto-written. | Integration | None (Mocked) | **KEEP** (Clinical safety invariant). |
| `test_intake_worker_registers_meal_once` | `test_pipeline.py:646` | Worker meal auto-registration. | Integration | None (Mocked) | **MODIFY** (Add clinician approval requirement). |
| `test_intake_worker_registers_meal_for_ambiguous_reading_message`| `test_pipeline.py:666`| Meal logged even if reading ambiguous. | Integration | None (Mocked) | **KEEP** (Data completeness invariant). |
| `test_intake_worker_does_not_duplicate_deterministic_meal`| `test_pipeline.py:687`| Deduplication of deterministic meals. | Integration | None (Mocked) | **KEEP** (Data integrity invariant). |
| `test_webhook_never_runs_intake_llm` | `test_pipeline.py:707` | Live webhook never invokes Gemini. | Integration | None (Mocked) | **KEEP** (Architecture boundary invariant). |
| `test_webhook_events_persisted_across_restarts`| `test_pipeline.py:739`| Webhook telemetry persisted to SQLite. | Integration | None (Mocked) | **KEEP** (Observability invariant). |

---

## 15. Mock & Demo Data Inventory

```
+---------------------------------------------------------------------------------------------------+
|                                       MOCK & DEMO ARTIFACTS                                       |
+------------------------------+------------------------------------+-------------------------------+
| Artifact / Logic Identifier  | Source Location                    | Real Logic vs. Demo Artifact  |
+------------------------------+------------------------------------+-------------------------------+
| Patient "Sunita Devi"        | app/core/seed.py:20                | DEMO ARTIFACT (Placeholder).  |
| UHID "AH-2026-0042"          | app/core/seed.py:20                | DEMO ARTIFACT (Placeholder).  |
| Phone "+917439030190"        | app/core/seed.py:15                | DEMO ARTIFACT (Test phone).   |
| Caregiver "Anil Kumar (son)" | app/core/seed.py:36                | DEMO ARTIFACT (Placeholder).  |
| Single Patient Auto-Adopt    | app/core/process.py:65-74          | DANGEROUS PROTOTYPE HACK.     |
| Mock Vision Plates Array     | app/core/nutrition.py:199-218      | MOCK ARTIFACT (No ML model).  |
| Synthetic Glucotype Engine   | scripts/demo.py:170-188            | DEMO GENERATOR (Gaussian).    |
| Operator Key "aahaar-2026"   | app/config.py:38                   | DEMO DEFAULT (Hardcoded).     |
| Render Webhook URL Default   | app/static/index.html:182          | DEMO ARTIFACT (Stale URL).    |
+------------------------------+------------------------------------+-------------------------------+
```

### Critical Separation: Real Logic vs. Demo Artifacts
* **Real Production-Grade Logic**:
  - Deterministic normalizer & phonetic regex refiner ([`app/core/parse.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/parse.py)).
  - Indian food nutritional taxonomy and volumetric carb calculator ([`app/core/nutrition.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/nutrition.py)).
  - Ingestion confirm loop and two-number role guard ([`app/core/process.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/process.py)).
  - Numerical telemetry analytics (TIR, slots, CVI, Pearson correlation) ([`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py)).
  - 270 DPI dual-panel Matplotlib charting engine ([`app/report/charts.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/report/charts.py)).
  - ReportLab Platypus publication-grade 2-page A4 PDF builder ([`app/report/pdf.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/report/pdf.py)).
* **Demo / Mock Artifacts to be Removed in Gate 01**:
  - Hardcoded patient seed scripts ([`app/core/seed.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/seed.py), [`scripts/seed_real.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/scripts/seed_real.py)).
  - Mock photo classification plate rotator in [`app/core/nutrition.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/nutrition.py#L199-L228).
  - Single-patient auto-adopt rule in [`app/core/process.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/process.py#L65-L74).
  - Hardcoded synthetic Gaussian glucose generators in [`scripts/demo.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/scripts/demo.py#L170-L188).

---

## 16. Security & Vulnerability Findings

### 16.1 Critical Severity Vulnerabilities
1. **Unsigned Inbound Meta Webhook Requests**:
   - **Location**: [`app/server/main.py:242`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/main.py#L242-L288).
   - **Finding**: While GET verification checks `hub.verify_token`, POST webhook handling does NOT validate Meta's `X-Hub-Signature-256` HMAC-SHA256 signature header using the Meta Application Secret.
   - **Impact**: Any external attacker can forge POST requests to `/api/v1/webhooks/whatsapp`, injecting fraudulent blood glucose readings and fabricated meal records directly into patient files.
2. **Unauthenticated PII & Clinical Data Exposure**:
   - **Location**: [`app/server/main.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/main.py#L303-L316), [`#L409-L457`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/main.py#L409-L457), [`#L496-L506`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/main.py#L496-L506).
   - **Finding**: Endpoints returning full patient registries (`GET /api/v1/patients`), live incoming WhatsApp feeds (`GET /api/v1/inbound/live`), medical reports (`GET /api/v1/patients/{pid}/report`), and complete conversational logs (`GET /api/v1/patients/{pid}/log`) have zero authentication.
   - **Impact**: Immediate HIPAA/DISHA compliance violation. Complete exposure of patient medical history, phone numbers, and full names.
3. **Unauthenticated Record Erasure**:
   - **Location**: [`app/server/main.py:507-528`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/main.py#L507-L528) (`POST /api/v1/patients/{pid}/clear-chat`).
   - **Finding**: Deletes all records from `raw_inbound` and `outbound` for a patient without requiring any authorization header or confirmation token.

### 16.2 High Severity Vulnerabilities
4. **Single Shared Symmetric Secret for Admin Operations**:
   - **Location**: [`app/config.py:38`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/config.py#L38).
   - **Finding**: Linking phone numbers, creating patient profiles, and dispatching direct doctor WhatsApp messages rely on a single plaintext environment variable (`AAHAAR_OP_KEY`, default `"aahaar-2026"`).
   - **Impact**: No individual operator attribution in audit logs. Compromise of this single string gives unrestricted administrative control.
5. **Dangerous Single-Patient Auto-Adoption**:
   - **Location**: [`app/core/process.py:65-74`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/process.py#L65-L74).
   - **Finding**: If only one patient exists in the database, any unknown incoming WhatsApp number is automatically bound to that patient's clinical file.
   - **Impact**: Accidental or malicious messages from random external numbers will permanently overwrite patient telephone records and corrupt clinical charts.
6. **Autonomous AI Mutation of Clinical Records**:
   - **Location**: [`app/core/ai_worker.py:180-279`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/ai_worker.py#L180-L279).
   - **Finding**: Decoupled background worker parses unrefined text and automatically inserts rows into the official `readings` and `meals` tables without clinical oversight.

---

## 17. Production Readiness Matrix

| Subsystem | Readiness Rating | Justification & Architectural Gaps |
| :--- | :--- | :--- |
| **Core Business Logic (Parsing & Nutrition)** | **PRODUCTION CANDIDATE** | High-performance, pure Python, zero-dependency, comprehensive test coverage (57 tests passing). |
| **Clinical Reporting (PDF & Charts)** | **PRODUCTION CANDIDATE** | Lab-grade ReportLab Platypus 2-page PDF generator; headless 270 DPI Matplotlib charting. |
| **Clinical Analytics Engine** | **PRODUCTION CANDIDATE** | Strictly descriptive formulas for TIR, adherence, meal-slot chronobiology, CVI, and Pearson $r$. |
| **Database Layer** | **PROTOTYPE** | Single-file SQLite. Lacks multi-tenancy, user accounts, canonical events, and Alembic migrations. |
| **Backend API (FastAPI)** | **FUNCTIONAL** | Clean ASGI structure, but unauthenticated read routes and shared static operator key. |
| **Identity & Authentication** | **NOT STARTED** | No user management, password hashing, JWT/session issuance, or MFA. Identity coupled to phone numbers. |
| **Authorization & RBAC** | **NOT STARTED** | Binary patient/caregiver phone check. Doctor, Nurse, Dietitian, and Coordinator roles absent. |
| **WhatsApp Channel Integration** | **FUNCTIONAL** | Meta Graph API v21.0 operational, but missing HMAC signature validation on inbound webhook. |
| **AI Integration & Worker** | **PROTOTYPE** | Model discovery works well, but autonomous database writes violate medical device safety standards. |
| **Clinician Web Workstation (P.L.A.T.E.)**| **PROTOTYPE** | Vanilla JS/HTML dashboard lacking authentication, state management, and modern component architecture. |
| **Mobile Application (THALI)** | **NOT STARTED** | No mobile codebase exists. Currently represented solely via WhatsApp conversational interface. |
| **Admin Web Console** | **NOT STARTED** | Minimal form inputs embedded in prototype dashboard; no dedicated administrative system. |
| **Testing & CI/CD** | **INTEGRATION READY** | 57 automated tests protecting invariants; fast execution (7.88s). Lacks linting, formatting, & CI/CD pipeline. |
| **Observability & Logging** | **PROTOTYPE** | SQLite audit and webhook_events tables exist, but structured JSON logging, metrics, and tracing are absent. |
| **Security & Compliance** | **NOT STARTED** | Unauthenticated PII exposure, plaintext shared secrets, unverified webhooks, no facility isolation. |

---

## 18. Reusable Assets Inventory

The following core modules represent high-value engineering assets that should be preserved and carried forward into the THALI × P.L.A.T.E. target architecture:

1. **[`app/core/nutrition.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/nutrition.py)**:
   - Complete taxonomy of 35+ Indian staple foods with calibrated densities, carbohydrates per 100g, and GI rankings.
   - Robust Hindi/Hinglish alias expansion dictionary.
   - Household katori volumetric portion math (Small 150ml, Medium 220ml, Large 350ml).
2. **[`app/core/parse.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/parse.py)**:
   - High-performance regex normalizer parsing blood glucose readings, meal items, and affirmations.
   - Ambiguity value detector (`ambiguous_reading_values`) preventing multi-reading errors.
3. **[`app/core/metrics.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/metrics.py)**:
   - Standardized calculations for Time-in-Range (TIR 70-180 mg/dL), Adherence Index, meal-slot PPBG (PB, PL, PD), CVI, and Pearson correlation ($r$).
4. **[`app/report/pdf.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/report/pdf.py) & [`app/report/charts.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/report/charts.py)**:
   - Production-ready ReportLab Platypus two-page lab-style PDF engine with DejaVuSans TTF typography.
   - Headless 270 DPI dual-panel Matplotlib chart compiler with target glycemic corridor and weekend shading.
5. **[`app/core/escalation.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/core/escalation.py)**:
   - Idempotent operational 9:00 PM nudge engine prioritizing caregivers over patients.
6. **[`app/server/whatsapp.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/whatsapp.py)**:
   - Clean channel abstraction with `SimulatorBackend` and Meta Cloud `CloudBackend`.

---

## 19. Technical Debt Inventory

1. **Database Schema Tooling**: Reliance on inline Python SQLite execution without version-controlled migrations (Alembic).
2. **Dynamic In-Function Imports**: Pervasive use of function-level imports across core modules to mask circular dependency coupling.
3. **Monolithic Controller**: [`app/server/main.py`](file:///Users/subhamdas/Documents/health-a-thon-BioCypher--master/app/server/main.py) bundles patient management, webhooks, reporting, live feeds, diagnostics, and static files into a single 622-line file.
4. **Synchronous Polling Overhead**: Frontend dashboard polls `/api/v1/inbound/live` every 3000ms, triggering backend analysis and unindexed database queries.
5. **Fragile UI State**: Frontend relies on direct string parsing and manual DOM manipulation (`innerHTML`), leading to XSS vulnerabilities and rendering glitches.
6. **Hardcoded Configuration Defaults**: Multiple modules hardcode the fallback phone number `+917439030190` and key `aahaar-2026`.

---

## 20. Architectural Risks

1. **Multi-Tenancy & Data Leakage Risk**: The current data model does not isolate records by hospital, clinic, or provider. A single misconfigured query exposes all patients across the entire deployment.
2. **Clinical Safety & Regulatory Risk**: Automated AI registration of clinical measurements in `ai_worker.py` creates legal and clinical liability under SaMD (Software as a Medical Device) guidelines.
3. **Webhook Impersonation Risk**: Lack of HMAC-SHA256 signature validation allows external bad actors to forge patient glucose logs and alter historical trends.
4. **Scalability Bottleneck**: SQLite file-locking under concurrent WAL transactions will bottleneck as multiple clinics, mobile apps, and WhatsApp webhooks read and write simultaneously.

---

## 21. Migration Candidates

| Existing Module / Component | Target Architecture Destination | Migration Action | Migration Rationale & Scope |
| :--- | :--- | :--- | :--- |
| `app/core/nutrition.py` | `thali_plate/services/nutrition/` | **KEEP / MOVE** | Direct drop-in into shared backend domain services. |
| `app/core/parse.py` | `thali_plate/services/nlp/parser.py` | **KEEP / MOVE** | Extract into canonical event parsing service. |
| `app/core/metrics.py` | `thali_plate/services/analytics/` | **KEEP / MOVE** | Direct drop-in into clinical analytics service. |
| `app/report/*` | `thali_plate/services/reporting/` | **KEEP / MOVE** | Becomes P.L.A.T.E. PDF evidence compilation service. |
| `app/core/escalation.py` | `thali_plate/workers/nudges.py` | **KEEP / MOVE** | Convert into scheduled Celery/Cron background worker. |
| `app/server/whatsapp.py` | `thali_plate/channels/whatsapp/` | **MODIFY** | Add HMAC signature validation and event queueing. |
| `app/core/datamodel.py` | `thali_plate/models/` | **REPLACE** | Replace with SQLAlchemy multi-tenant models & Alembic. |
| `app/core/ai_worker.py` | `thali_plate/workers/ai_intake.py`| **MODIFY** | Remove autonomous database writes; require human sign-off. |
| `app/server/main.py` | `thali_plate/api/v1/` | **REFACTOR** | Deconstruct into modular FastAPI APIRouters with JWT/RBAC. |
| `app/static/*` | Deprecate & Archive | **REPLACE** | Replaced by THALI mobile app & P.L.A.T.E. web console. |

---

## 22. Unknowns & Decisions Requiring Human Input

1. **Target Database Engine**: Does the team intend to deploy PostgreSQL for production multi-tenant scalability, or remain on embedded SQLite for local edge clinic deployments?
2. **Mobile App Framework Selection**: Is the universal role-aware mobile application (THALI × P.L.A.T.E.) to be built using **Flutter** or **React Native**?
3. **AI Provider Redundancy**: Should Google Gemini remain the primary LLM, or must the system support local on-premise models (e.g. Ollama / Llama 3) for clinics with intermittent internet connectivity?
4. **Caregiver Binding Policy**: The current prototype limits each patient to exactly **one active caregiver**. Should the target THALI model support multiple concurrent family caregivers?
5. **AI Intake Inscription Boundary**: Should AI-extracted readings be stored in a staging table (`staged_readings`) requiring explicit clinician or patient confirmation before moving to the official ledger?

---

## 23. Recommended GATE 01 Preparation

Before commencing Gate 01 (Architecture Reconciliation & Domain Design), the following preparatory steps are recommended:

1. **Define Unified Identity & Role Model**: Specify schemas for `User`, `Role`, `Facility`, `Clinician`, `Patient`, and `Caregiver` with support for role switching within the universal mobile app.
2. **Establish Canonical Event Model**: Design a unified, append-only `clinical_events` schema unifying meal logs, glucose pricks, symptoms, medication events, and notes.
3. **Implement Database Migration Tooling**: Scaffold Alembic for SQLAlchemy to manage multi-tenant database evolutions cleanly.
4. **Formulate Webhook Security Standards**: Draft middleware implementing Meta HMAC-SHA256 signature verification (`X-Hub-Signature-256`).
5. **Design AI Human-in-the-Loop Protocol**: Establish a staged validation queue ensuring generative AI outputs never mutate clinical state autonomously.

---

## Final Status Declaration

```
================================================================================
GATE 00 STATUS: READY FOR ARCHITECTURE RECONCILIATION
================================================================================
The reconnaissance audit is complete. All 23 audit sections have been verified
against actual repository source code. The existing Aahaar codebase provides 
robust, production-candidate domain logic (parsers, nutritional taxonomy, 
clinical metrics, and PDF reporting), while identifying critical gaps in 
identity, multi-tenancy, authentication, and mobile client architecture that 
must be addressed in Gate 01.
================================================================================
```
