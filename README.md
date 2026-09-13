# Aahaar — Glycemic Context for the Diabetes OPD

Health-a-thon 2026 · **Diabetes Care** track · **Doctor / Care-Team facing** solution
Anchor use case: **Consultation Readiness & Patient Journey Review**

**Concept:** Aahaar turns a patient's real meal photos + real glucose readings into a
**2-page lab-style "Glycemic Context" report** the doctor reads before/at consultation. It is
**assistive, not diagnostic**: it organises real data; the doctor decides. Never a dose,
never a prediction, never a diagnosis.

Plans, PPT outline, Round 1 answers and the full product spec live in `../plan-and-ppt/`
(kept outside this git repo).

## What is in this repo

```
app/
  config.py         every switch: target range (70–180), katori sizes, mock-vision, channel
  core/             pure-Python engine — no web framework, easy to test
    nutrition.py    Indian-food table + mock vision / text classifier (doctor-only carbs · GI)
    parse.py        turns a WhatsApp/simulator message into a typed, safe event
    process.py      guards, confirm loop, replies (patient NEVER sees carb/GI numbers)
    metrics.py      descriptive metrics: TIR (70–180), adherence, weekday/weekend, CVI…
    report.py       report context assembled from logged data
    escalation.py   9 PM missed-logging nudge (max 1/day, caregiver-first)
    datamodel.py    SQLite store
    seed.py         demo patient + window
  report/           chart PNGs + the 2-page A4 PDF renderer
  server/           FastAPI wiring + WhatsApp plug-ins (Simulator / Cloud)
  static/           no-build vanilla-JS dashboard served by FastAPI
  tests/            safety + behaviour invariants (pytest)
  scripts/          demo (end-to-end) and seeding helpers
```

## Run the end-to-end demo (a full simulated 2-week window)

```bash
pip install --break-system-packages -r requirements.txt   # if starting fresh
python3 -m scripts.demo --days 14          # logs ~13 meals + 26 readings, builds the PDF
python3 -m scripts.demo --days 14 --desktop   # also copies the PDF to the Windows Desktop
python3 -m scripts.demo --days 14 --close      # optional: close the window when logging ends
```
The demo leaves the logging window **open**, so the dashboard chat panel keeps accepting
messages (try `fasting 128` or a plate text like `2 roti, dal, sabzi`).
Output lands in `reports/Aahaar-Doctor-Report-1-<window-start>.pdf`.

## Run the web dashboard

```bash
# point the server at the demo database so it has data:
AAHAAR_DB=aahaar-demo.db python3 -m uvicorn app.server.main:app --port 8000
# open http://localhost:8000
```

On first launch with an empty DB the server auto-seeds a demo patient, so it never starts blank.
The dashboard's **Messages** tab lets you play the WhatsApp chat (pick patient/caregiver/unknown
sender, send a reading or a plate) to watch the guard + confirm loop live.

### Deploying (Render / any web host)

Use the checked-in entrypoint so the seed and the server share ONE database and the port
binds quickly (charts/PDF are rebuilt on demand from live day-log data — nothing heavy runs
at boot):

```bash
# start command:
bash scripts/start.sh
```

`scripts/start.sh` exports `AAHAAR_DB` (default `aahaar.db` — override via env), seeds `--days 14`,
then runs uvicorn on `$PORT`. On Render, `scripts.demo` automatically skips the chart/PDF render
step (`RENDER` env) so boot takes <1s; pass `--report` to force rendering at seed time.

## Tests

```bash
python3 -m pytest tests -q
```

The suite enforces the product's hard safety rules: no risky/clinical wording in the report,
patient replies never mention carbs/GI, unregistered numbers are refused, only confirmed
meals feed the report, one caregiver bound per patient, TIR classification over 70–180,
weekday/weekend split, and nudge idempotency.

## Real WhatsApp channel (Phase 5)

The channel layer already has a `CloudBackend` (Meta WhatsApp Cloud API). To switch the
server from the simulator to real WhatsApp, set `AAHAAR_WHATSAPP=cloud`,
`META_PHONE_ID`, `META_TOKEN`, expose a public HTTPS webhook (e.g. cloudflared) and add
event routing — the full click-by-click beginner walkthrough lives in
**[docs/WHATSAPP_DEMO.md](docs/WHATSAPP_DEMO.md)**. The only thing that needs *you* is a
free Meta developer account + a few numbers whitelisted (5 max); we'll do the live session
together ahead of the build sprint.

## Product guardrails (never cross these)

- No diagnosis, no prediction/forecasting, no risk scores, no dose advice.
- Patient-facing text shows **portion only** (Small/Medium/Large katori); carbs & GI are
  doctor-only.
- Only **confirmed** meal estimates enter the report; only the patient + ONE caregiver can
  log; all data is fake/anonymised in this repo.