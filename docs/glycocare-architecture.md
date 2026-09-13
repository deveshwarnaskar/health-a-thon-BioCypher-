# GlycoCare — System Architecture & Blueprint

This document records the architecture of the Aahaar/GlycoCare diabetes
logbook as built and verified (90-test baseline, plus the intelligent-intake
regression suite), and — as a blueprint — the full GlycoCare continuo-care
monolith that this repository deliberately does **not** ship.

## 1. Product boundary (what this system IS)

A **clinic-grade diabetes logging + compliant report tool**, not a medical
advisor:

- Patients and ONE bound caregiver log readings and meals in any language.
- The clinic sees live day-logs, metrics (TIR, patterns), trend charts and a
  report export.
- Nobody — patient, dashboard, AI — ever sees/displays carb/GI numbers or
  analysis wording; the report avoids "hyper/hypo/recommend/predict/dose" etc.

Guarded by tests (`tests/test_pipeline.py`): FORBIDDEN_IN_REPORT and
FORBIDDEN_IN_PATIENT_REPLY are enforced, role guards, active-window guards,
reading range sanity (glucose 20–600 is loggable; anything else refused), one
caregiver bound per patient, confirm-loop so only confirmed meals feed the
report.

## 2. Logical layers

```
WhatsApp / dashboard
   │  raw inbound rows stored FIRST (webhook never interprets)
   ▼
app/core/process.py      IngestService  role/window guard, 100% raw audit,
                                        quiet answers, meal proposal loop
   ▼
app/core/parse.py        deterministic NLP: values, tags, times, sizes,
                                        references, deletions, dated edits
   ▼
app/core/datamodel.py    Store (sqlite3): readings, meals, raw/outbound,
                         audit, webhook events, avoid list
   ▼
app/core/intake_ai.py    off-webhook analysis of STORED rows (dashboard
                         trigger / background worker) + Gemini input-collection
   ▼
app/core/ai_worker.py    IntakeWorker: writes readings/meals, sends follow-ups
                         through the same outbound channel composers use
   ▼
app/core/metrics.py / report.py / charts  ->  dashboard + report
```

### 2.1 The webhook is store-first and silent

`process.handle()` persists the raw message, runs the deterministic parser, and
returns at most ONE short app-like confirmation. Follow-up ANSWERS
(tag/duplicate/ambiguous-value), size-only answers ("100ml"), meal references
("not the one i told") and delete commands are **quiet** at the webhook: the
dashboard/AI intake is their single, coherent responder.

### 2.2 The deterministic layer is the ONLY writer

All logging decisions are made locally:

- **Readings** — a single in-range number is a confirmed reading; "230 or 330"
  becomes a pending candidate row and the patient picks the number; repeated
  numbers collapse to one; clock minutes ("8 30 am"), portion counts ("100 ml",
  "do katori") can never be misread as glucose.
- **Context tags** — fasting / post-prandial / random rewards; "morning"/"subah"
  are timing, never fasting; "khane se pehle" is gently discouraged, never logged.
- **Times** — meals and readings honour the day/time the text names ("yesterday
  evening near 3pm", "14 july shaam 3 baje", "today at 8 30 am" -> 08:30), with
  a real-calendar-date backdate for past days. Part-of-day defaults stand in
  only when no explicit hour is said.
- **Multiple readings** — "8am 130, 9am 145" / "subah 130 aur shaam 150" register
  each value at its own time.
- **Edits** — a dated correction ("kal 8am wala galat tha, 140 tha") updates that
  reading; "130 not 120" edits the latest; `delete that reading` / `ye khana
  delete karo` remove rows. Old meals are kept and marked superseded.
- **Meals** — dish phrases are kept exact ("chole bhature" never splits into
  "white rice"); never fabricated from junk ("the meal i told was wrong" logs
  no dish); portion sizes are stored verbatim ("100ml", "do katori") plus a
  small/medium/large letter; carbs/GI are never written.

### 2.3 Gemini is an input-collection assistant, never a writer

When `GEMINI_API_KEY` is set, Gemini only (a) words ONE follow-up question in
the patient's own language, and (b) names dishes/readings that are anchored to
words/numbers the patient actually wrote. Values Gemini cannot anchor to real
message numbers are discarded. If Gemini is missing, the deterministic notifier
takes over and nothing breaks. Localised replies are translated only for
regional scripts, bounded, emoji/number-preserving, and blocked if Gemini
invents clinical wording (target/dose/insulin/prescribe/medication/consult…).

## 3. Data model (sqlite3)

- `patients`, `caregivers`, `windows` (scheduling)
- `readings` (value, tag, reading_type, ts, status, candidates_json, raw_id)
- `meals` (items_json, portion, portion_text, ts, status, superseded_by)
- `raw_inbound` (refined_json keeps intent + registration markers)
- `outbound`, `audit`, `webhook_events`, `avoid_items`

Idempotency: every raw row carries `registered` / `meal_registered` markers;
duplicate suppressors exist for readings (same-day+hour+value) and meals (same
dish set, same day).

## 4. Verification

`python3 -m pytest -q` -> **104 passed** covering: safety wording, role guards,
confirm loop, metrics/TIR, backdating, exact food phrases, portion handling,
references/deletions, multi/multilingual readings, dated edits, detect_language
(scripts + Hinglish), and localise-reply fallback.

---

## 5. GlycoCare full-continuum blueprint (NOT in this repo)

The following is the agreed design for the larger product. It is intentionally
**out of scope** of this repository and pipeline: no medical-advice messages,
no automation that contacts a patient's phone number without the clinic's
explicit release.

- **One family canvas.** A patient journeys through monitoring windows; the
  canvas holds blood-glucose readings, meals, weight/BP (removed of typed
  numbers from patient-facing text), medication compliance, symptoms, activity —
  all attached to a live-timestamped logbook.
- **Continuum layers.** Clinic + patient + nutritionist + (future) educator all
  view the same data behind role-scoped dashboards: live day-log, TIR/metrics,
  trend charts, report export. Escalation applies only within a window and only
  as flags for the clinic.
- **Multilingual by design.** Understanding in any language (deterministic
  layer + optional LLM grounding); replies mirror the patient's script.
- **Audit-first.** Every inbound text, every AI decision, every registration —
  including corrections/deletions — is an audit event; the timeline is
  reconstructable.
- **WhatsApp decoupling.** The webhook is store-first; AI is a separate
  consumer; outbound uses the same channel composers use. WhatsApp remains
  dashboard-released, never AI-autonomous.

Deployment: single process (fastapi + sqlite3), `scripts/start.sh`, dashboard
builds chart PNGs on demand; Render boot path seeds DB only.