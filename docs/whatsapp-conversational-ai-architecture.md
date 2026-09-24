# WhatsApp Conversational AI Layer — Architecture & Implementation (Spec §0–§40)

**Product:** THALI (Telemetry & Household Assistive Logbook for Interventions)
**Module:** WhatsApp Inbound Conversational Layer
**Status:** Implemented (deterministic-first, AI-enabled)
**Scope:** session state machine (§5), intent taxonomy (§6), structured output
contract (§7–§8), multilingual extraction (§9–§11), deterministic-first
strategy (§12), safety firewall (§13–§16), confirmation/correction (§17–§18),
care-task drafts (§23), reminders (§19–§22), voice (§24), handoff (§26),
provenance/telemetry (§27–§34), architecture boundaries (§35–§40).

---

## 1. Layering & Architecture Boundaries

The import-boundary audit
(`tests/unit/architecture/test_import_boundaries.py`) forbids `backend.application/**`
from importing `backend.infrastructure/**` or `pydantic`. Following the exact
precedent of `ops/intake_text.py` (which imports `backend.infrastructure.parsing`),
the deterministic parsing lives with the other parsers:

```
backend/infrastructure/parsing/
    intent_firewall.py                 # legacy gate (pre-existing)
    hinglish_parser.py                 # pre-existing
    nutrition_taxonomy.py              # pre-existing
    conversation/                     # NEW — spec §6–§11
        taxonomy.py                    # ConversationIntent (19-intent superset) + DidResolvedIntent
        extractors.py                  # Indic/Bengali/Arabic digit normalization, entity extractors
        schema.py                      # StructuredIntent, entities, Confidence, Provenance*, SafetyFlag (pydantic)

backend/application/ops/
    contracts.py                       # DeliveryOutcome, AuditAction (pre-existing)
    handlers.py                        # WhatsAppIntakeHandler + conversation_engine seam
    conversation/                      # NEW — orchestration (no infra/pydantic imports)
        engine.py                      # ConversationEngine, EngineOutcome, in-memory SessionStore
        state.py                       # ConversationSession/State/DraftKind + fingerprints
        safety.py                      # SafetyPolicyEngine (§13–§16)
        confirm.py                     # neutral prompt/ack builders (§17)
        reminders.py                   # ReminderPolicy — quiet hours + cooldown (§20)
        prompts.py                     # L1–L4 layered prompt contracts (§30)
        providers.py                   # DeterministicConversationProvider + SarvamConversationProvider (§33)
        telemetry.py                   # PHI-free counters (§32)
        fallback.py                    # graceful degradation (§31)

backend/infrastructure/persistence/
    models/conversation_models.py                     # ConversationSessionModel, PatientChannelPrefModel
    ops/conversation_session_store.py                 # SqlAlchemyConversationSessionStore (§5)
    alembic/versions/0012_conversation_sessions.py    # migration + RLS

backend/interfaces/cli/worker.py                     # wiring (engine + durable store + provider)
tests/unit/ops/test_conversation_engine.py           # 21 engine tests
tests/unit/infrastructure/test_conversation_session_store.py  # durable store tests
```

The application layer only touches `infrastructure.parsing.conversation`
(deterministic parsing) — exactly as `intake_text.py` touches
`infrastructure.parsing`; everything else stays outside the seam.

---

## 2. Integration Seam with the Legacy Inbound Flow

`WhatsAppIntakeHandler` gains an optional `conversation_engine: Any = None`
constructor parameter (no default import, no touch to the legacy path). On each
inbound message, after `_deliver_deferred_welcome` and before the legacy
`IntentFirewall.evaluate`:

```python
outcome = conversation_engine.handle(...)
if outcome.handled:
    self._send_reply(..., interactive=outcome.interactive)
    audit(...); uow.commit()
    return DeliveryOutcome.SUCCESS
```

Engine returns `None` (not handled) for everything owned by the legacy flow —
so the 990-test legacy happy path is byte-identical when the engine is absent.

**Engine ownership:**

| Owned by the engine | Deferred to legacy flow |
| --- | --- |
| MEDICATION_CONFIRMATION, CARE_TASK, TIMELINE_REQUEST, LANGUAGE_CHANGE, DOCUMENT_UPLOAD, VOICE_MESSAGE, HANDOFF_TO_CARE_TEAM, safety blocks (§13–§16) | GLUCOSE_LOG, MEAL_LOG, CONFIRM, CANCEL, CORRECTION/CORRECT, STATUS, HELP + legacy-supported CONVERSATIONAL |

**Critical ordering:** the safety gate runs *before* legacy deferral. A message
requesting diagnosis, dosage advice, emergency help, cross-patient data, or
non-health topics is intercepted even if the deterministic classifier would
have labelled it CONVERSATIONAL — only legacy-owned clinical logs (glucose,
meal, confirm, cancel, correct, status) are exempt, because their values are
still domain-validated downstream.

---

## 3. Session State Machine (§5)

`ConversationState`: `IDLE` → `AWAITING_{GLUCOSE,MEAL,MEDICATION,TASK}_CONFIRM`
→ `IDLE`, plus `AWAITING_DOCUMENT_UPLOAD`, `HANDOFF_OPEN`, `BLOCKED`.

**Hard rules:**

- **No PHI on the session row.** A session carries only `state`, `draft_kind`
  and a `draft_fingerprint` that points at the draft — the observation itself
  lives (already persisted by its domain handler in PENDING/awaiting-confirm
  state) in its own tenant-scoped table.
- **Deterministic transitions only.** AI never mutates the session; `handled`
  and `interactive` are decided by the engine's state machine.
- **Survives restart.** The durable `SqlAlchemyConversationSessionStore`
  persists every `save()`; a bound `app.current_tenant_id` is set before each
  query so the FORCE RLS policy (migration 0012) isolates the row tenant-wise.

**Fingerprints** (`state.py`) — `g:{value}:{tag}`, `m:{normalized}:{portion}`,
`med:{medication}:{when}`, `t:{normalized}` — let CONFIRM/CANCEL replies match
the exact pending draft, guarding against confirm-on-stale-draft.

---

## 4. Intent Taxonomy & Multi-lingual Extraction (§6–§11)

`ConversationIntent` is a 19-intent superset. The offline classifier
`DidResolvedIntent` runs a documented ladder: legacy-bridge intents →
safety-sensitive intents → medication → time-offset reminders → language
change → sugar/meal timeline → care task → global fallbacks. Sample verified
outputs:

| Text | Intent |
| --- | --- |
| `subah ki dawai le li` | MEDICATION_CONFIRMATION |
| `kal 8 baje yaad dilana` | CARE_TASK |
| `meri maa ka sugar batao` | UNKNOWN (cross-patient ⇒ safety block) |
| `sugar check kar li` | REMINDER_RESPONSE |
| `mujhe diabetes hai kya` | GENERAL_DIABETES_TRACKING_HELP |
| `bahut takleef ho rahi hai` | HANDOFF_TO_CARE_TEAM |
| `change language to bengali` | LANGUAGE_CHANGE |
| `140 fasting` / `2 roti dal` | GLUCOSE_LOG / MEAL_LOG (legacy) |
| `write me a poem` | NON_HEALTH_REQUEST (safety block) |

Common drug names (metformin, glipizide, dapagliflozin, …) are included in the
medication markers so medication-taking messages are never misclassified as
care tasks.

**Digit normalization** translates Devanagari (`१४०`), Bengali (`২৩০`), and
Arabic-Indic (`٧٨٩`) digits before glucose/meal parsing; ambiguous readings
(e.g. `shayad 230 or 330`) keep `value_mg_dl=None` and are rejected rather than
guessed.

---

## 5. Safety Firewall (§13–§16)

`SafetyPolicyEngine` is consulted by the engine on *every* payload before any
other handling:

1. **NO clinical interpretation.** Confirmation and timeline replies quote the
   patient's own values; the reply bank carries no interpretation and a
   forbidden-word guard (`FORBIDDEN_INTERPRETIVE_WORDS`) blocks replies that
   would read like medical advice.
2. **Blocked topics** → interception with a concrete replied guidance hint
   (`_GUIDANCE` bank): emergency (references 108/112 and defers triage),
   diagnosis, dosage, injection, cross-patient, non-health.
3. **Escalation hint** is carried in `EngineOutcome.emergency` and the reply
   surfaces it in-device; the outbox carries the audit trail.

No offline fallback, no shadow interpretation: when Sarvam is unavailable the
deterministic provider still extracts safe, conservative responses (§31).

---

## 6. Confirmation, Correction, Care Tasks, Reminders (§17–§23)

- **Medication:** extract → `mark_draft` → interactive confirm prompt → button
  `confirm_yes` → `RecordMedicationAdministrationHandler` when a matching
  *active* plan exists, otherwise a neutral acknowledgment (never a phantom
  adherence record).
- **Care task (§23):** task entity extracted → draft → confirm (`haan`)
  → `Notification` (REMINDER) + a `ChannelMessageQueued` self-reminder.
  `ReminderPolicy` (§20) enforces quiet hours (22:00–07:00 IST) and a 2.5 h
  cooldown; the reminder template params are mirrored into the notification's
  correlation context.
- **Cancel:** a CNCL read inside AWAITING_CONFIRM clears the draft pointer and
  replies with the paired cancel acknowledgment.
- **Timeline request:** returns a *neutral list* of the patient's own recent
  entries — never a trend conclusion.

---

## 7. Voice, Handoff, Provenance, Telemetry (§24–§34)

- **Voice (§24):** an inbound voice message with a transcript is treated as
  plain text; an empty transcript returns `EMPTY_TRANSCRIPT_REPLY`; `audio/*`
  media types are whole-message routed.
- **Handoff (§26):** pain/escalation intents produce a
  `HANDOFF_TO_CARE_TEAM` outcome flagged for outbox escalation.
- **Provenance (§27):** any engine-produced reply carries
  `provenance={"mode": "...", "deterministic": True/False, ...}` in
  `EngineOutcome`; confirmations quote the draft fingerprint so audit rows link
  back to the exact observation. Domain events (e.g. `GlucoseObservationConfirmed`)
  flow through the normal outbox.
- **Telemetry (§32):** PHI-free counters (`intents_seen`, `blocks_triggered`,
  `confirm_prompts_sent`, …) are thread-safe and intentionally contain no
  patient identifiers; observable via the existing metric collectors.

---

## 8. Providers & Deterministic-First Strategy (§12, §33)

`ConversationAIProvider` has exactly two implementations:

- `DeterministicConversationProvider` — the default; identity, persistence,
  reminders, nutrition and safety are always deterministic. Used when Sarvam
  is unconfigured/unreachable so the product still functions offline.
- `SarvamConversationProvider` — wraps `SarvamClient`; used only for NLU intent
  extraction and natural wording. Wrapped in its own try/except at wiring time;
  the engine never allows provider failure to change clinical state.

`ai_extract_intent` remaps the model's output onto the structured contract and
never fabricates confidence above what the taxonomer proved.

---

## 9. Persistence & RLS (migration 0012)

- `whatsapp_conversation_sessions` — one row per `(tenant_id, patient_id)`;
  `state`, `draft_kind`, `draft_fingerprint`, `context` (JSONB on Postgres),
  `updated_at`; unique `(tenant_id, patient_id)`.
- `patient_channel_prefs` — per `(patient_id, channel)`: `preferred_language`,
  `quiet_hours_start/end`, `last_reminder_at`.
- Foreign keys cascade tenant→organization, patient; RLS FORCE + tenant
  isolation policy + app-role grants, identical pattern to migration 0006.
- `alembic upgrade head` applied to the rehearsal Postgres:
  `postgresql+psycopg://thali_user@127.0.0.1:5432/thali_db` — 0011 → 0012.

---

## 10. Tests

- `tests/unit/ops/test_conversation_engine.py` — 21 tests: legacy deferral,
  non-health/diagnosis/dosage/emergency/injection/cross-patient blocks,
  medication draft → interactive button confirm → plan-matched administration,
  care-task draft → confirm → REMINDER notification + self-reminder, task
  cancel, timeline neutral list, language change, Devanagari/Bengali digit
  extraction, ambiguous-reading rejection, forbidden-word wording checks,
  offline determinism.
- `tests/unit/infrastructure/test_conversation_session_store.py` — durable
  store: fresh-IDLE default, save/recover across restart, tenant row
  separation, reset persists.
- `tests/integration/test_alembic_migrations.py` — upgrade-to-head + downgrade
  to base now covers the 0012 tables (sqlite dialect path).
- Import-boundary audit passes with the narrowed `ops/conversation` carve-out.
- Full suite: **1016 passed**.

---

## 11. Live Wiring & Operation

`backend/interfaces/cli/worker.py::build_worker`:

```python
conv_ai = DeterministicConversationProvider()          # default, offline-safe
if _sarvam_configured(settings):                       # → SarvamConversationProvider
    ...
conversation_engine = ConversationEngine(
    clock=clock, id_gen=id_gen, ai_provider=conv_ai,
    session_store=SqlAlchemyConversationSessionStore(session_factory),  # durable §5
)
intake._conversation_engine = conversation_engine
```

Operational notes:

- Restart the worker after deploying this layer (`--poll` mode; log
  `/tmp/thali-worker.log`). Live worker re-flagged with the engine is PID-based
  and must be re-invoked on deploy.
- Backend API (`uvicorn --factory` :8000) is unaffected.
- Outbox consumers must have the `NA:`-style handlers for `meal_observation.confirmed`
  events — the current wild worker logs `outbox event without a registered
  handler` for those (pre-existing).
- Migration 0012 is reversible (`alembic downgrade -1` drops both tables,
  disables RLS).