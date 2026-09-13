# GATE 00 — Verification Report

**Document verified:** `GATE_00_EXISTING_SYSTEM_AUDIT.md` (1023 lines, 23 sections)
**Repository:** `/Users/subhamdas/Documents/health-a-thon-BioCypher--master`
**Verification mode:** Read-only. No source files moved, edited, deleted, or refactored. No database or dependency changes.

---

## Verification Method & Evidence

| Item | Evidence |
| :--- | :--- |
| Runtime | `.venv` Python **3.14.7** |
| Installed packages | fastapi 0.141.1 · uvicorn 0.52.4 · pydantic 2.13.5 · matplotlib 3.11.2 · numpy 2.5.3 · reportlab 5.0.1 · httpx 0.28.1 · pytest 9.1.1 · pymupdf 1.28.2 |
| Dependency pins | `requirements.txt` — 8 lines, all match audit §8 |
| Test execution | `python -m pytest -q` → **57 passed, 2 warnings, 2.66s** (audit reports 7.88s; run-time is hardware-dependent) |
| Test inventory | Exactly 57 `test_*` functions — 16 in `tests/test_linking.py`, 41 in `tests/test_pipeline.py`; **every cited line number matches the audit exactly** |
| API inventory | 26 FastAPI routes catalogued; matches audit §9 |
| File inventory | Directory + file tree verified against audit §2 |

---

## Section-by-Section Verification Status

| Section | Status | Notes |
| :--- | :--- | :--- |
| 1. Scope / non-diagnostic framing | VERIFIED | Consistent with README, dashboard notices, and report disclaimers. |
| 2. Repository tree | VERIFIED (2 discrepancies) | `aahaar.db` omitted from tree; LICENSE mislabeled as BSD-3-Clause. |
| 3. Technology inventory | VERIFIED (2 discrepancies) | NumPy attributed to `metrics.py` (actually `charts.py`); "match syntax" not present. |
| 4. Architecture flow diagrams (4.1–4.3) | VERIFIED | All referenced functions/classes resolve (`webhook_inbound`, `record_raw_received`, `IngestService.handle`, `parse_inbound`, `refine_text_local`, `classify_text`, `CloudBackend.send_bulk`, `analyze_intake`, `_local_notifier`, `IntakeWorker._save_refined`, `_maybe_register`, `_maybe_register_meal`, `build_report`, `latest_report_context`, `compute_window_metrics`, `charts.render`, `pdf.render`, `render_html`). |
| 5. Subsystem analysis | VERIFIED (1 discrepancy) | html_preview claims "SVG embeds" — actual embeds are PNG. |
| 6. Database schema | VERIFIED | `datamodel.SCHEMA` L27–L75 matches; `raw_inbound.message_id` added via ad-hoc ALTER, consistent with "effective schema". Indexes match. |
| 7. Deployment scenario | VERIFIED | Framing/illustrative; no factual contradiction found. |
| 8. Dependencies | VERIFIED | Pins + installed versions satisfy every stated requirement. |
| 9. API endpoint & auth matrix | VERIFIED | 26 routes; the audit's unauth/auth classification matches source exactly (no-auth `GET /patients`, `POST webhook`, `clear-chat`, debug endpoints; `X-Aahaar-Key` = `operator_key`, default `aahaar-2026`). |
| 10. Evaluation criteria / component evidence | VERIFIED | All test-function line references check out exactly. |
| 11. Metrics tables | VERIFIED (1 note) | Line refs `metrics.py#L165-L167`, `#L170-L173`, `#L175`, `#L237-L249` verified. Adherence "coverage" is a demo print, not an assertion. |
| 12. Reporting architecture | VERIFIED | Modular chain `datamodel → metrics → report → {charts,pdf,html_preview}`, headless Matplotlib Agg, 2-page ReportLab PDF, DejaVuSans. |
| 13. Frontend analysis | VERIFIED | 6 tabs, 646-line `app.js` (verified: 646 lines), `setInterval(...,3000)` at `app.js:554`, `alert()` error handling, `innerHTML` DOM manipulation. |
| 14. Test architecture | VERIFIED (1 note) | 57/57 pass; measured 2.66s vs documented 7.88s. |
| 15. Mock & demo inventory | VERIFIED (1 discrepancy) | Render webhook URL ref mislocated. All mock-table anchors otherwise exact. |
| 16. Security findings | VERIFIED | All confirmed: unsigned webhook POST (no `X-Hub-Signature-256`), unauth PII exposure, unauth `clear-chat`, plaintext shared key, single-patient auto-adopt, autonomous AI writes (no staging). |
| 17–22. Readiness matrix / risks / migration / unknowns | VERIFIED | Qualitative assessments consistent with observed code; no factual contradictions. |
| 23. Gate 01 recommendations | VERIFIED | Directionally sound (identity/RBAC, event model, migrations, HMAC, AI HITL). |

---

## Discrepancies & Corrections

---

### AUDIT CLAIM
Technology Inventory §3 lists "Analytics Engine: **NumPy** & Python statistics" and cites `app/core/metrics.py#L9-L10`.

### ACTUAL STATE
`app/core/metrics.py` imports only `math` and `statistics` (`import math` / `import statistics`). NumPy is imported (`import numpy as np`) at `app/report/charts.py:18` and used only by the charting subsystem, not `metrics.py`.

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §3 · `app/core/metrics.py` · `app/report/charts.py`

### SEVERITY
LOW — Incorrect component attribution in the tech inventory; affects both modules' trust here but not the actual analytics engine behavior.

### CORRECTION
Attribute NumPy to the charts/reporting stack: "NumPy (charting) | `app/report/charts.py#L18`; Python `statistics`/`math` (analytics) | `app/core/metrics.py#L9-L10`".

---

### AUDIT CLAIM
Technology Inventory §3 lists "Python ≥3.10 features: dataclasses, `from __future__ import annotations`, **match syntax**, typing unions (`tuple[int, ...]`)" as heavy usage.

### ACTUAL STATE
Dataclasses, `from __future__ import annotations`, and `X | Y` unions are genuinely pervasive. However, **no Python `match`/`case` statements exist anywhere in project source** (only matches are regex assignments like `num_match = re.search(...)` and `match`/`case` occurrences inside `.venv` site-packages, e.g. `typing_extensions`).

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §3 · repo-wide grep over `*.py` (excluding `.venv`)

### SEVERITY
LOW — Cosmetic inventory inaccuracy; no behavioral impact.

### CORRECTION
Remove "match syntax" from the feature list, or reword to "intensive use of dataclasses, `from __future__ import annotations`, PEP 604 unions, and `tuple[int, ...]`".

---

### AUDIT CLAIM
Repository tree §2 lists LICENSE as "[KEEP] **BSD-3-Clause Open Source License**".

### ACTUAL STATE
`LICENSE` (32 lines) is a proprietary private license: "Copyright © 2026 BioCypher … All rights reserved. NOT FOR PUBLIC DISTRIBUTION." It grants evaluation rights only to the Health-a-thon 2026 organisers/judging panel and explicitly states "THIS LICENSE DOES NOT GRANT ANY PUBLIC LICENSE OR DISTRIBUTION RIGHTS." It is **not** BSD-3-Clause, MIT, or any open-source license.

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §2 · `LICENSE`

### SEVERITY
MEDIUM — Legal classification error in the inventory; mislabels the distribution posture of the submission and could mislead the migration/archiving plan.

### CORRECTION
Relabel the LICENSE row as "[ARCHIVE] Proprietary / All Rights Reserved (NOT FOR PUBLIC DISTRIBUTION) — Health-a-thon 2026 evaluation license".

---

### AUDIT CLAIM
Repository tree §2 inventory omits `aahaar.db` (lists only `aahaar-demo.db`, `aahaar-demo.db-shm`, `aahaar-demo.db-wal`).

### ACTUAL STATE
Repo root contains `aahaar.db` in addition to the three `aahaar-demo.db*` files. `aahaar.db` is a second SQLite database (gitignored, like the demo DBs).

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §2 · repo root listing

### SEVERITY
LOW — Incomplete file inventory; the presence of a non-demo production-shaped DB file may warrant attention before Gate 01.

### CORRECTION
Add `aahaar.db` to the repository tree (e.g. a new row "[REVIEW] SQLite database file — confirm whether a stale production-shaped artifact").

---

### AUDIT CLAIM
Subsystem analysis §5.15 states the HTML report preview embeds "shared chart PNG/SVG chart embeds" (i.e., SVG support implied).

### ACTUAL STATE
`app/report/html_preview.py::render_html` embeds **PNG** images sourced from the chart endpoints (`/api/v1/patients/{pid}/report/charts/top` and `/bottom`); there is no SVG rendering anywhere in the reporting stack.

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §5.15 · `app/report/html_preview.py`

### SEVERITY
LOW — Minor technical mischaracterization of the preview subsystem.

### CORRECTION
Change wording to "shared 270 DPI PNG chart embeds".

---

### AUDIT CLAIM
§15 "Mock & Demo Data Inventory" row: "Render Webhook URL Default | **app/static/index.html:182** | DEMO ARTIFACT (Stale URL)".

### ACTUAL STATE
`app/static/index.html:182` is the placeholder text `Loading diagnostics...`, not a URL. The stale hardcoded Render callback URL `https://aahaar-573f.onrender.com/api/v1/webhooks/whatsapp` actually lives at **`app/static/app.js:204`** (and is mirrored as `expected_callback_url` at `app/server/main.py:182`).

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §15 · `app/static/app.js` · `app/static/index.html` · `app/server/main.py`

### SEVERITY
LOW — Wrong source citation; the underlying "stale Render URL default" finding is real and preserved.

### CORRECTION
Re-point the row to `app/static/app.js:204` (also mirror `app/server/main.py:182`).

---

### AUDIT CLAIM
§16.1 item 2 cites "medical reports" exposure at `app/server/main.py#L496-L506`.

### ACTUAL STATE
`app/server/main.py:495-506` is the `GET /api/v1/patients/{pid}/log` handler (conversational log + audit). The report GETs (`GET /api/v1/patients/{pid}/report`, `/report/file`, `/report/preview`) live a few lines later (~L540-L600). Both the log and report endpoints are equally unauthenticated, so the **finding is fully correct**; only the precise citation is off.

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §16.1 · `app/server/main.py`

### SEVERITY
LOW — Finding stands; citation misaligns route↔lines.

### CORRECTION
Amend citation to the actual report-route line range, e.g. `#L540-L600`, or note "log + report endpoints".

---

### AUDIT CLAIM
§14 and §17 state the suite "passes cleanly in 7.88s".

### ACTUAL STATE
`pytest -q` measured **2.66s** on this machine for 57 passed. Runtime depends on hardware/OS; the functional claim (57/57 pass) is verified exactly.

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §14, §17

### SEVERITY
LOW — Informational; not a defect in the audit.

### CORRECTION
Optionally record the measured time ("measured 2.66s on verification machine") instead of pinning a single duration.

---

### AUDIT CLAIM
§11 "Adherence Index" row: "Automated Test Coverage: **Covered via `scripts/demo.py#L145`**".

### ACTUAL STATE
`scripts/demo.py:145` is `"adherence": metrics["adherence_index"],` — a **print statement** in the demo's metrics dump, not an automated test assertion. `compute_window_metrics` computes adherence and it is exercised indirectly through report-context integration tests, but there is no dedicated assertion on the adherence formula.

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §11 · `scripts/demo.py`

### SEVERITY
LOW — Coverage claim conflates a demo print with an automated test.

### CORRECTION
Rewrite as "Printed by the demo at `scripts/demo.py#L145`; exercised indirectly via report-context tests — no dedicated assertion."

---

### AUDIT CLAIM
Line-range citations: `app/core/process.py:65-74` (auto-adopt), `app/core/ai_worker.py:180-224` / `225-279` / `180-279`, `get_patient_by_phone` at `L137-L153`.

### ACTUAL STATE
Auto-adopt block is `process.py:65-73` (74 is boundary). `ai_worker._maybe_register` spans **L180-L220** and `_maybe_register_meal` spans **L225-L278** (the §16.2 combined cite L180-L279 is 1 line over). `get_patient_by_phone` spans `L137-L152`. All cited ranges bound the correct code; differences are ±1–4 lines at margins.

### FILE
`GATE_00_EXISTING_SYSTEM_AUDIT.md` §16 / earlier citations · `app/core/process.py`, `app/core/ai_worker.py`

### SEVERITY
LOW — Off-by-one/off-by-few citation margins; no misdirected references.

### CORRECTION
Adjust to `process.py:65-73`, `ai_worker.py:180-220` and `225-278`.

---

## Verification Verdict

The audit's substantive claims are all confirmed against actual source: every module/class/function cited exists; all 26 routes and the auth matrix match; the SQLite schema and indexes match; all 9 documented dependencies satisfy the pinned requirements; all 57 test functions exist at the exact cited line numbers and **pass**; the security findings (unsigned webhook, unauthenticated PII exposure, shared plaintext operator key, single-patient auto-adopt, autonomous AI clinical writes) are real; and the frontend/reporting/mock/demo characterizations hold.

The only deviations are one MEDIUM (LICENSE mislabeled as BSD-3-Clause when it is a private license) and a set of LOW citation/label inaccuracies. None of them undermine any audit conclusion, security finding, or Gate 01 recommendation, and none change the audit's aggregated status.

**Classification summary:**
- CRITICAL: 0
- HIGH: 0
- MEDIUM: 1
- LOW: 9 (incl. 2 informational notes)

## Final Status Declaration

`GATE_00_EXISTING_SYSTEM_AUDIT.md` reflects the actual state of the repository with materially accurate architecture, inventory, and security reporting. All findings stand; the corrections above are cosmetic/pinpointing and should be folded into the next revision before Gate 01 commences.

GATE 00 VERIFIED