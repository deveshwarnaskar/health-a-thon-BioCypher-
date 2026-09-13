"""Safety + behaviour invariants for the Aahaar pipeline.

These are the checks that keep the product OUT of the disqualified zone:
no diagnosis/prediction/advice wording, patient never sees carb/GI numbers,
unregistered numbers are refused, the confirm loop means only confirmed meals
feed the report, and one-caregiver bound per patient.
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.config import Settings
from app.core.datamodel import Store
from app.core.escalation import due_escalations
from app.core.metrics import compute_window_metrics
from app.core.parse import parse_inbound
from app.core.process import IngestService

FORBIDDEN_IN_REPORT = [
    "hyper", "hypo", "recom", "should", "advise", "must ", "risk",
    "predict", "dose", "prescrib",
]
FORBIDDEN_IN_PATIENT_REPLY = ["carbs", "carb ", "glycemic index", "gi ", "estimate is "]


def _handle(store, cfg, pid, raw):
    return IngestService(store, cfg).handle({**{"patient_id": pid}, **raw})


def _full_text(parts) -> str:
    return " ".join(str(p) for p in parts).lower()


# ---- parse layer -----------------------------------------------------
def test_parse_reading_from_text():
    p = parse_inbound({"patient_id": 1, "kind": "text", "text": "fasting 126"}, Settings())
    assert p.is_reading and p.reading == 126 and p.reading_tag == "fasting"


def test_parse_out_of_range_reading_refused():
    p = parse_inbound({"patient_id": 1, "kind": "text", "text": "fasting 900"}, Settings())
    assert p.kind == "refusal"


def test_parse_confirm_portion():
    p = parse_inbound({"patient_id": 1, "kind": "text", "text": "correct s"}, Settings())
    assert p.kind == "confirm" and p.portion_letter == "s"


# ---- role guards -------------------------------------------------------
def test_unregistered_number_refused(seeded, store, cfg):
    pid, _ = seeded
    replies = _handle(store, cfg, pid,
                      {"sender_phone": "+919111111111", "kind": "text", "text": "roti dal"})
    assert replies and "clinic to link" in replies[0].body.lower()
    assert store.meals_for_window(store.list_windows(pid)[0]["id"], confirmed_only=False) == []
    assert store.readings_for_window(store.list_windows(pid)[0]["id"]) == []


def test_two_number_rule(seeded, store, cfg, intake):
    pid, wid = seeded
    w = store.get_window(wid)
    # patient + one caregiver are fine: webhook captures silently, the
    # dashboard AI intake is the sole logger.
    for phone in ("+919000000001", "+919000000002"):
        replies = _handle(store, cfg, pid, {"sender_phone": phone, "kind": "text",
                                            "text": "fasting 120"})
        assert replies == []
    intake(store, cfg)
    assert any(abs(r["value"] - 120) < 0.5 for r in store.readings_for_window(wid))
    # appoint a new caregiver -> the previous binding is replaced, not stacked
    store.set_caregiver(pid, "+919000000009", "Someone Else")
    replies = _handle(store, cfg, pid, {"sender_phone": "+919000000009", "kind": "text",
                                        "text": "fasting 120"})
    assert replies == []
    # an entirely random number is still refused
    replies = _handle(store, cfg, pid, {"sender_phone": "+919111111111", "kind": "text",
                                        "text": "fasting 120"})
    assert replies and "clinic to link" in replies[0].body.lower()


# ---- confirm loop ---------------------------------------------------------
def test_only_confirmed_meals_count(seeded, store, cfg):
    pid, wid = seeded
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "photo",
                              "photo_path": "x.jpg"})  # pending, not confirmed
    m1 = compute_window_metrics(store, cfg, wid)
    assert m1["meals_count"] == 0

    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "yes"})
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "roti dal"})
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "yes"})
    m2 = compute_window_metrics(store, cfg, wid)
    assert m2["meals_count"] == 2


def test_portion_correction_applies(seeded, store, cfg):
    pid, wid = seeded
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "roti dal"})
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "correct l"})
    meals = store.meals_for_window(wid, confirmed_only=True)
    assert len(meals) == 1 and meals[0]["status"] == "corrected" and meals[0]["portion"] == "l"


def test_reading_sanity_guard(seeded, store, cfg):
    pid, wid = seeded
    replies = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                                        "text": "900"})
    assert replies and "didn't understand" in replies[0].body.lower()
    assert store.readings_for_window(wid) == []


# ---- metrics --------------------------------------------------------------
def test_tir_classification_70_180(seeded, store, cfg, intake):
    pid, wid = seeded
    for vals in ([120, 150, 190, 60],):
        for v in vals:
            _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                                      "text": f"fasting {v}"})
    intake(store, cfg)
    m = compute_window_metrics(store, cfg, wid)
    assert m["tir"]["total"] == 4
    assert m["tir"]["in"] == 50 and m["tir"]["above"] == 25 and m["tir"]["below"] == 25


def test_weekday_weekend_ppbg_split(seeded, store, cfg, intake):
    pid, wid = seeded
    from datetime import date, timedelta
    w = store.get_window(wid)
    day = date.fromisoformat(w["start_date"])
    end = date.fromisoformat(w["end_date"])
    sat = tue = None
    while day <= end:
        if day.weekday() == 5 and sat is None:
            sat = day
        if day.weekday() == 1 and tue is None:
            tue = day
        day += timedelta(days=1)
    assert sat and tue
    for d, v in ((sat, 200), (tue, 150)):
        _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                                  "text": f"post {v}", "ts": d.isoformat() + "T12:00:00"})
    intake(store, cfg)
    m = compute_window_metrics(store, cfg, wid)
    assert m["weekday_ppbg"] == 150 and m["weekend_ppbg"] == 200
    assert m["weekend_ppbg_delta"] == 50


# ---- postprandial meal slots (post-breakfast / lunch / dinner) --------------
def test_parse_meal_slot_readings_from_text():
    cfg = Settings()
    for text, tag in (("post breakfast 168", "postbreakfast"),
                      ("post lunch 180", "postlunch"),
                      ("post dinner 200", "postdinner"),
                      ("after lunch 170", "postlunch"),
                      ("after dinner 190", "postdinner"),
                      ("pb 152", "postbreakfast")):
        p = parse_inbound({"patient_id": 1, "kind": "text", "text": text}, cfg)
        assert p.is_reading and p.reading_tag == tag, text


def test_post_slot_inferred_from_preceding_meal(seeded, store, cfg, intake):
    pid, wid = seeded
    from datetime import date
    day = date.fromisoformat(store.get_window(wid)["start_date"])
    d = day.isoformat()
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "roti dal", "ts": d + "T09:00:00"})
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "yes", "ts": d + "T09:01:00"})
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "post 158", "ts": d + "T10:30:00"})
    intake(store, cfg)
    m = compute_window_metrics(store, cfg, wid)
    assert m["post_breakfast"]["count"] == 1 and m["post_breakfast"]["mean"] == 158
    assert m["post_lunch"]["count"] == 0 and m["post_dinner"]["count"] == 0


def test_post_slot_stats_split_weekday_weekend(seeded, store, cfg, intake):
    pid, wid = seeded
    from datetime import date, timedelta
    w = store.get_window(wid)
    day = date.fromisoformat(w["start_date"])
    end = date.fromisoformat(w["end_date"])
    sat = tue = None
    while day <= end:
        if day.weekday() == 5 and sat is None:
            sat = day
        if day.weekday() == 1 and tue is None:
            tue = day
        day += timedelta(days=1)
    assert sat and tue
    for d, v in ((sat, 200), (tue, 150)):
        _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                                  "text": f"post dinner {v}", "ts": d.isoformat() + "T20:00:00"})
    intake(store, cfg)
    m = compute_window_metrics(store, cfg, wid)
    assert m["post_dinner"]["count"] == 2
    assert m["post_dinner"]["weekday"] == 150 and m["post_dinner"]["weekend"] == 200


def test_chart_context_has_three_slot_series(seeded, store, cfg, intake):
    pid, wid = seeded
    from datetime import date
    day = date.fromisoformat(store.get_window(wid)["start_date"])
    d = day.isoformat()
    for txt, ts in (("post breakfast 150", "T10:00:00"),
                    ("post lunch 170", "T15:00:00"),
                    ("post dinner 200", "T21:00:00")):
        _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                                  "text": txt, "ts": d + ts})
    intake(store, cfg)
    from app.core.report import build_report_context
    ctx = build_report_context(store, cfg, wid)
    ch = ctx["charts"]
    assert len(ch["pb_values"]) == 1 and ch["pb_values"][0] == 150
    assert len(ch["pl_values"]) == 1 and ch["pl_values"][0] == 170
    assert len(ch["pd_values"]) == 1 and ch["pd_values"][0] == 200


# ---- report language safety ------------------------------------------------
def test_report_context_has_no_forbidden_language(seeded, store, cfg):
    pid, wid = seeded
    from app.core.report import build_report_context
    text = _full_text(_collect(build_report_context(store, cfg, wid)))
    for w in FORBIDDEN_IN_REPORT:
        assert w not in text, f"forbidden report phrase found: {w!r}"


def test_patient_replies_never_mention_carbs_or_gi(seeded, store, cfg):
    pid, _ = seeded
    replies = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                                        "text": "roti dal sabzi"})
    text = _full_text([r.body for r in replies])
    for w in FORBIDDEN_IN_PATIENT_REPLY:
        assert w not in text, f"patient-facing reply leaked: {w!r}"


# ---- escalation ------------------------------------------------------------
def test_escalation_idempotent_and_daily_cap(seeded, store, cfg):
    pid, wid = seeded
    now = datetime.now().replace(hour=21, minute=5)
    first = due_escalations(store, cfg, now=now)
    assert len(first) == 1
    store.record_outbound(wid, "caregiver", "text", first[0]["body"], first[0]["unique_key"])
    second = due_escalations(store, cfg, now=now)
    assert second == []
    # next morning the nudge is allowed again (different day key)
    later = now.replace(hour=7)
    assert due_escalations(store, cfg, now=later) == []  # before 21:00 nothing fires


def _collect(ctx: dict) -> list:
    strings = []
    if isinstance(ctx, dict):
        for k, v in ctx.items():
            if k in ("charts", "series"):
                continue
            if isinstance(v, str):
                strings.append(v)
            elif isinstance(v, dict) and k == "patient":
                strings += list(v.values())
            elif isinstance(v, list) and v and isinstance(v[0], str):
                strings += v
            elif isinstance(v, dict):
                strings += _collect(v)
    return strings


# ---- Natural Language (Hindi & English) Tests ------------------------------
def test_natural_language_glucose_reading():
    cfg = Settings()
    # Conversational Hinglish
    p1 = parse_inbound({"patient_id": 1, "kind": "text", "text": "aaj subah fasting sugar 138 aaya"}, cfg)
    assert p1.is_reading and p1.reading == 138 and p1.reading_tag == "fasting"

    # Conversational English
    p2 = parse_inbound({"patient_id": 1, "kind": "text", "text": "My blood sugar after lunch was 175 mg/dl"}, cfg)
    assert p2.is_reading and p2.reading == 175 and p2.reading_tag == "postlunch"

    # Khali pet (Hindi for fasting)
    p3 = parse_inbound({"patient_id": 1, "kind": "text", "text": "khali pet 118"}, cfg)
    assert p3.is_reading and p3.reading == 118 and p3.reading_tag == "fasting"

    # Dinner ke baad
    p4 = parse_inbound({"patient_id": 1, "kind": "text", "text": "dinner ke baad sugar 195"}, cfg)
    assert p4.is_reading and p4.reading == 195 and p4.reading_tag == "postdinner"


def test_natural_language_meal_and_confirm():
    cfg = Settings()
    # Everyday Hindi meal words
    p1 = parse_inbound({"patient_id": 1, "kind": "text", "text": "maine 2 chapati aur sabji khayi"}, cfg)
    assert p1.is_meal and len(p1.items) >= 1

    # Hindi confirmation
    p2 = parse_inbound({"patient_id": 1, "kind": "text", "text": "haan theek hai"}, cfg)
    assert p2.is_confirm

    # Hindi portion correction
    p3 = parse_inbound({"patient_id": 1, "kind": "text", "text": "chota"}, cfg)
    assert p3.is_confirm and p3.portion_letter == "s"

    # Novel uncatalogued dish (never rejected)
    p4 = parse_inbound({"patient_id": 1, "kind": "text", "text": "had a bowl of oats and fruits"}, cfg)
    assert p4.is_meal and len(p4.items) >= 1


def test_typo_correction_and_talking_back_ai(seeded, store, cfg, intake):
    pid, wid = seeded
    # Typo: 'sugr 14o' (letter 'o' instead of zero) -> recovered as 140 mg/dL.
    # The webhook is silent; the AI intake registers + confirms.
    r1 = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "sugr 14o"})
    assert r1 == []

    # Typo: 'fastng 125'
    r2 = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "fastng 125"})
    assert r2 == []

    intake(store, cfg)
    readings = store.readings_for_window(wid)
    assert any(abs(r["value"] - 140) < 0.5 for r in readings)
    assert any(abs(r["value"] - 125) < 0.5 for r in readings)

    # Ambiguous input -> Talking back AI asks polite clarification
    r3 = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "kuch samajh nahi aa raha"})
    assert r3 and ("samajh nahi aaya" in r3[0].body or "didn't understand" in r3[0].body)


def test_all_raw_patient_text_is_logged_in_database(seeded, store, cfg):
    pid, wid = seeded
    # Even weird / broken / confusing text is 100% saved in the database
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "random broken text 9999"})
    raw_logs = store.raw_inbound_log(wid)
    assert len(raw_logs) >= 1
    assert any("random broken text 9999" in log["raw_text"] for log in raw_logs)

def test_prick_keyword_parsing(seeded, store, cfg, intake):
    pid, wid = seeded
    # Patient sends 'prick 142' -> recognized as blood sugar 142 (webhook silent,
    # dashboard AI registers it).
    r1 = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "prick 142"})
    assert r1 == []

    # Patient sends 'finger prick 135'
    r2 = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "finger prick 135"})
    assert r2 == []

    intake(store, cfg, limit=100)
    readings = store.readings_for_window(wid)
    assert any(rd["value"] == 142.0 for rd in readings)
    assert any(rd["value"] == 135.0 for rd in readings)


def test_live_inbound_api_and_unlinked_visibility(tmp_path):
    from fastapi.testclient import TestClient
    from app.server.main import create_app
    from app.config import Settings

    client = TestClient(create_app(cfg=Settings(db_path=str(tmp_path / "test_live.db"), whatsapp="simulator")))
    # 1. Post a message from an unlinked external number
    r = client.post("/api/v1/inbound", json={
        "sender_phone": "+919988776655",
        "kind": "text",
        "text": "prick 155"
    })
    assert r.status_code == 200

    # 2. Check live inbound endpoint
    live = client.get("/api/v1/inbound/live").json()
    assert "messages" in live
    assert any("prick 155" in m["raw_text"] and m["sender_phone"] == "+919988776655" for m in live["messages"])


def test_audit_defenses_zero_readings_and_pending_matching(tmp_path, store, cfg):
    """Test that zero readings chart render does not crash and newest_pending matches digits."""
    from app.report.charts import render_top
    from app.report.pdf import _deltastr

    # 1. Delta string formatting
    assert _deltastr(150.0, 140.0) == "+10.0"
    assert _deltastr(140.0, 150.0) == "-10.0"
    assert _deltastr(None, 100) == "—"

    # 2. Render top chart with empty series (zero readings)
    empty_ch = {
        "dates": ["2026-09-01", "2026-09-02"],
        "fpg": [], "fpg_values": [],
        "ppbg": [], "ppbg_values": [],
        "pb": [], "pb_values": [],
        "pl": [], "pl_values": [],
        "pd": [], "pd_values": [],
        "corridor_low": 70.0,
        "corridor_high": 180.0,
        "weekends": [False, False],
    }
    out_png = str(tmp_path / "top_empty.png")
    # Must not raise ValueError
    res = render_top(empty_ch, out_png)
    assert res == out_png

    # 3. Newest pending matching across +91 and 91
    pid = store.add_patient("Test Pending", "AH-PEND-1", "+919876543210")
    wid = store.open_window(pid, "2026-09-01", "2026-09-14")
    meal_id = store.propose_meal(wid, "+919876543210", "patient", "text",
                                 [{"name": "roti", "portion": "m", "carbs": 24, "gi": "med"}],
                                 "m", 220, 24, "med", 0.9)
    # Search with digits only (Meta format)
    found = store.newest_pending("9876543210")
    assert found is not None
    assert found["id"] == meal_id

    # Test mark_pending_stale sets status to stale
    store.mark_pending_stale("9876543210")
    assert store.newest_pending("9876543210") is None


# ---- store-first webhook capture + AI gate ---------------------------------
def test_webhook_store_first_duplicate_skip(tmp_path):
    from fastapi.testclient import TestClient
    from app.server.main import create_app
    c = TestClient(create_app(cfg=Settings(db_path=str(tmp_path / "dup.db"), whatsapp="simulator")))
    payload = {
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "contacts": [{"wa_id": "917439030190"}],
                    "messages": [{"from": "917439030190", "id": "WAMID-STR-1",
                                  "type": "text", "text": {"body": "fasting 124"}}],
                },
            }]
        }]
    }
    r1 = c.post("/api/v1/webhooks/whatsapp", json=payload)
    assert r1.status_code == 200 and r1.json() == {"ok": True, "processed": 1}
    # Same Meta message id redelivered must not double-process
    r2 = c.post("/api/v1/webhooks/whatsapp", json=payload)
    assert r2.json() == {"ok": True, "processed": 1}
    log = c.get("/api/v1/patients/1/log").json()
    inb = [m for m in log["inbound"] if m.get("raw_text") == "fasting 124"]
    assert len(inb) == 1, "duplicate Meta message id must be skipped"


def test_llm_gated_off_live_path_by_default(monkeypatch, cfg):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-gating-test")
    from app.core.ai import call_llm_reasoning, get_last_ai_status
    res = call_llm_reasoning("fasting 123", "Test", cfg=cfg)
    assert res is None
    assert get_last_ai_status()["last_status"] == "gated_offlive"



# ---- decoupled AI intake notifier -----------------------------------------
def test_intake_local_notifier_confirms_and_asks(cfg):
    from app.core.intake_ai import analyze_intake
    # Reading with explicit tag -> confirmed in ONE message, no missing fields.
    r = analyze_intake("fasting 128", "Ramesh", cfg=cfg)
    assert r.intent == "reading" and r.missing == [] and r.should_reply is True
    assert "Logged sugar 128" in r.reply and "fasting" in r.reply.lower()
    # Reading without context tag -> the confirmation also asks the tag.
    r = analyze_intake("sugar 130", "Ramesh", cfg=cfg)
    assert r.intent == "reading" and r.missing == ["reading_tag"] and r.should_reply is True
    assert "fasting" in r.reply or "khane" in r.reply
    # Meal without portion -> the confirmation also asks the portion.
    r = analyze_intake("roti dal sabzi", "Ramesh", cfg=cfg)
    assert r.intent == "meal" and r.missing == ["portion"] and r.should_reply is True
    # Meal with portion -> complete confirmation.
    r = analyze_intake("2 roti dal small", "Ramesh", cfg=cfg)
    assert r.intent == "meal" and r.missing == [] and r.should_reply is True
    assert "Logged khana" in r.reply
    # Reading hint but no number -> asks for the value.
    r = analyze_intake("sugar only", "Ramesh", cfg=cfg)
    assert r.missing == ["reading_value"] and r.should_reply is True


def test_intake_never_medical_advice(cfg):
    from app.core.intake_ai import analyze_intake
    forbid = ["target", "dose", "insulin", "medicine", "medication", "doctor",
              "lifestyle", "exercise", "avoid", "parhej", "suggest", "consult"]
    for text in ("sugar 130", "roti dal sabzi", "kuch samajh nahi aa raha hai",
                 "fasting", "khana ho gaya"):
        r = analyze_intake(text, "Ramesh", cfg=cfg)
        low = r.reply.lower()
        assert not any(w in low for w in forbid), (
            f"intake reply crossed into medical advice for {text!r}: {r.reply!r}")


def test_intake_worker_picks_stored_rows_and_routes_reply(store, cfg):
    from app.core.ai_worker import IntakeWorker
    pid = store.add_patient("Test Cel", "TC-1", "+919123456780")
    store.record_raw_received("+919123456780", "sugar 130", message_id="WAMID-WORK-1")
    sent = []
    def send_func(out):
        sent.append(out)
        return True
    w = IntakeWorker(store, cfg, send_func=send_func, interval=5.0)
    # Phase 1: analyze-only (the default) must NOT touch WhatsApp.
    s1 = w.run_once(limit=10, should_send=False)
    assert s1["analyzed"] == 1 and s1["sent"] == 0
    assert len(sent) == 0
    rows = store.raw_inbound_all(limit=10)
    tag = [r for r in rows if r["message_id"] == "WAMID-WORK-1"][0]
    import json as _json
    refined = _json.loads(tag["refined_json"])
    assert refined["intent"] == "reading" and refined["missing"] == ["reading_tag"]
    assert refined["followup_sent"] is False
    # Phase 2: dashboard-driven send releases exactly one follow-up.
    s2 = w.run_once(limit=10, should_send=True, send_gap=0.0)
    assert s2["analyzed"] == 0 and s2["sent"] == 1
    assert len(sent) == 1 and ("fasting" in sent[0].body or "khane" in sent[0].body)
    tag = [r for r in store.raw_inbound_all(limit=10)
           if r["message_id"] == "WAMID-WORK-1"][0]
    assert _json.loads(tag["refined_json"])["followup_sent"] is True
    # Idempotent: a third run must not re-analyze or re-send.
    s3 = w.run_once(limit=10, should_send=True, send_gap=0.0)
    assert s3["analyzed"] == 0 and s3["sent"] == 0
    assert len(sent) == 1


def test_analyze_stored_endpoint_operator_keyed_and_send(tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.core.datamodel import Store
    from app.server.main import create_app
    db = str(tmp_path / "analyze.db")
    store = Store(db)
    store.add_patient("Test Cel", "TC-2", "+919234567890")
    store.record_raw_received("+919234567890", "roti dal", message_id="WAMID-ANZ-1")
    store.close()
    c = TestClient(create_app(cfg=Settings(db_path=db, whatsapp="simulator",
                                           operator_key="aahaar-2026",
                                           ai_intake_on_read_send=False)))
    # Wrong / missing operator key -> 403.
    assert c.post("/api/v1/analyze/stored").status_code == 403
    assert c.post("/api/v1/analyze/stored",
                  headers={"X-Aahaar-Key": "wrong"}).status_code == 403
    # Default run is analyze-only: no WhatsApp messages are sent.
    r = c.post("/api/v1/analyze/stored", json={"limit": 25},
               headers={"X-Aahaar-Key": "aahaar-2026"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True and data["analyzed"] == 1 and data["sent"] == 0
    feed = c.get("/api/v1/inbound/live").json()["messages"]
    hit = [m for m in feed if m["raw_text"] == "roti dal"][0]
    assert hit["ai"] is not None and hit["ai"]["intent"] == "meal"
    # Explicit send=true releases the follow-up via the outbound channel.
    r2 = c.post("/api/v1/analyze/stored", json={"limit": 25, "send": True},
                headers={"X-Aahaar-Key": "aahaar-2026"})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["ok"] is True and data2["analyzed"] == 0 and data2["sent"] == 1
    assert c.get("/api/v1/analyze/status").json()["ok"] is True


def test_live_inbound_auto_analyzes_and_pushes_followup_once(tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.core.datamodel import Store
    from app.server.main import create_app
    db = str(tmp_path / "auto.db")
    store = Store(db)
    store.add_patient("Test Auto", "TA-1", "+919345678901")
    store.record_raw_received("+919345678901", "sugar 145", message_id="WAMID-AUTO-1")
    store.close()
    c = TestClient(create_app(cfg=Settings(db_path=db, whatsapp="simulator",
                                           operator_key="aahaar-2026")))
    # No operator key, no manual analyze call: the live feed read auto-analyzes
    # AND pushes the follow-up to the patient exactly once.
    r = c.get("/api/v1/inbound/live")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    hit = [m for m in msgs if m["raw_text"] == "sugar 145"][0]
    assert hit["ai"] is not None and hit["ai"]["intent"] == "reading"
    assert hit["ai"]["should_reply"] is True
    st = c.get("/api/v1/analyze/status").json()
    assert st["last_summary"]["analyzed"] == 1 and st["last_summary"]["sent"] == 1
    # A second read must not re-analyze or re-send (one follow-up per message).
    c.get("/api/v1/inbound/live")
    st2 = c.get("/api/v1/analyze/status").json()
    assert st2["last_summary"]["analyzed"] == 0 and st2["last_summary"]["sent"] == 0


def test_live_inbound_on_read_send_off_keeps_hints_only(tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.core.datamodel import Store
    from app.server.main import create_app
    db = str(tmp_path / "auto-off.db")
    store = Store(db)
    store.add_patient("Test Off", "TO-1", "+919356789012")
    store.record_raw_received("+919356789012", "sugar 145", message_id="WAMID-AUTO-2")
    store.close()
    c = TestClient(create_app(cfg=Settings(db_path=db, whatsapp="simulator",
                                           operator_key="aahaar-2026",
                                           ai_intake_on_read_send=False)))
    c.get("/api/v1/inbound/live")
    st = c.get("/api/v1/analyze/status").json()
    assert st["last_summary"]["analyzed"] == 1 and st["last_summary"]["sent"] == 0


def test_ambiguous_reading_values():
    from app.core.parse import ambiguous_reading_values
    assert ambiguous_reading_values(
        "pata nhi shayad 230 or 330 i ate a whole steak with red wine") == [230.0, 330.0]
    assert ambiguous_reading_values("sugar 145") == []
    assert ambiguous_reading_values("fasting 126") == []
    assert ambiguous_reading_values("2 roti dal") == []


def test_webhook_suppresses_meal_confirm_for_ambiguous_reading(seeded, store, cfg):
    pid, _wid = seeded
    # Ambiguous reading + meal in one message: NO meal portion-confirm leaves
    # the webhook ([]) and the row is audited; no reading is registered.
    outs = _handle(store, cfg, pid, {
        "sender_phone": "+919000000001", "kind": "text",
        "text": "pata nhi shayad 230 or 330 i ate a whole steak with red wine"})
    assert outs == []
    assert any(a["action"] == "reading_ambiguous"
               for a in store.audit_log())
    # Sanity: an ordinary meal still gets its portion-confirm.
    outs2 = _handle(store, cfg, pid, {
        "sender_phone": "+919000000001", "kind": "text", "text": "roti dal"})
    assert outs2 and "Correct portion" in outs2[0].body


def test_intake_worker_registers_resolved_reading_once(seeded, store, cfg):
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    store.record_raw_received("+919000000001", "sugar 145",
                              message_id="WAMID-REG-1")
    w = IntakeWorker(store, cfg, send_func=lambda out: True)
    s1 = w.run_once(limit=10, should_send=False)
    assert s1["analyzed"] == 1
    readings = store.readings_for_window(wid)
    assert len(readings) == 1 and abs(readings[0]["value"] - 145) < 0.5
    assert any(a["action"] == "reading_registered"
               for a in store.audit_log())
    # Rerun must not double-register.
    w.run_once(limit=10, should_send=False)
    assert len(store.readings_for_window(wid)) == 1


def test_intake_worker_keeps_ambiguous_reading_pending(seeded, store, cfg):
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    store.record_raw_received("+919000000001",
                              "pata nahi shayad 230 or 330",
                              message_id="WAMID-AMB-1")
    w = IntakeWorker(store, cfg, send_func=lambda out: True)
    w.run_once(limit=10, should_send=False)
    # An ambiguous reading is KEPT in the log as 'needs confirmation' — a
    # pending row with the candidate values, never a guessed number.
    readings = store.readings_for_window(wid)
    assert len(readings) == 1
    assert readings[0]["status"] == "pending"
    assert readings[0]["candidates_json"] is not None
    import json as _json
    rows = store.raw_inbound_all(limit=10)
    tag = [r for r in rows if r["message_id"] == "WAMID-AMB-1"][0]
    fj = _json.loads(tag["refined_json"])
    assert fj["reading_status"] == "ambiguous"
    assert fj["reading_candidates"] == [230.0, 330.0]
    assert any(a["action"] == "reading_pending" for a in store.audit_log())
    # Rerun must not double-book the pending row.
    w.run_once(limit=10, should_send=False)
    assert len(store.readings_for_window(wid)) == 1


def test_intake_worker_registers_meal_once(seeded, store, cfg):
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    store.record_raw_received("+919000000001", "roti dal",
                              message_id="WAMID-MEAL-1")
    w = IntakeWorker(store, cfg, send_func=lambda out: True)
    s1 = w.run_once(limit=10, should_send=False)
    assert s1["analyzed"] == 1
    meals = store.meals_for_window(wid, confirmed_only=False)
    assert len(meals) == 1 and meals[0]["status"] == "pending"
    assert meals[0]["source"] == "ai"
    items = json.loads(meals[0]["items_json"])
    assert {it["item"] for it in items} == {"roti", "dal"}
    assert any(a["action"] == "meal_registered"
               for a in store.audit_log())
    # Rerun must not double-register the meal.
    w.run_once(limit=10, should_send=False)
    assert len(store.meals_for_window(wid, confirmed_only=False)) == 1


def test_intake_worker_registers_meal_for_ambiguous_reading_message(seeded, store, cfg):
    # Ambiguous reading: the reading is NEVER auto-registered, but the food the
    # patient described still gets logged into the meal record by the AI.
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    store.record_raw_received(
        "+919000000001",
        "pata nahi shayad 230 or 330 i ate a whole steak with red wine",
        message_id="WAMID-MEAL-AMB-1")
    w = IntakeWorker(store, cfg, send_func=lambda out: True)
    w.run_once(limit=10, should_send=False)
    readings = store.readings_for_window(wid)
    assert len(readings) == 1 and readings[0]["status"] == "pending"
    meals = store.meals_for_window(wid, confirmed_only=False)
    assert len(meals) == 1
    assert meals[0]["source"] == "ai" and meals[0]["status"] == "pending"
    assert any(a["action"] == "meal_registered"
               for a in store.audit_log())
    w.run_once(limit=10, should_send=False)
    assert len(store.meals_for_window(wid, confirmed_only=False)) == 1


def test_intake_worker_does_not_duplicate_deterministic_meal(seeded, store, cfg):
    # Ordinary meal message: the deterministic webhook already proposed the meal
    # and asked for the portion confirm. The AI worker must NOT add a second row.
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    store.record_raw_received("+919000000001", "roti dal",
                              message_id="WAMID-MEAL-DEDUP-1")
    outs = _handle(store, cfg, pid, {
        "sender_phone": "+919000000001", "kind": "text", "text": "roti dal"})
    assert outs and "Correct portion" in outs[0].body
    w = IntakeWorker(store, cfg, send_func=lambda out: True)
    w.run_once(limit=10, should_send=False)
    meals = store.meals_for_window(wid, confirmed_only=False)
    assert len(meals) == 1  # AI does not add a second 'roti, dal' row
    import json as _json
    rows = store.raw_inbound_all(limit=10)
    tag = [r for r in rows if r["message_id"] == "WAMID-MEAL-DEDUP-1"][0]
    assert _json.loads(tag["refined_json"])["meal_registered"] is True


def test_intake_worker_backdates_meal_to_referred_day(seeded, store, cfg):
    # "yesterday i ate 2 roti and dal" must land on the day the text refers to,
    # not on the message's own receive date.
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    store.record_raw_received("+919000000001",
                              "yesterday i ate 2 roti and dal",
                              message_id="WAMID-MEAL-BD-1",
                              ts="2026-09-13T08:00:00")
    IntakeWorker(store, cfg, send_func=lambda out: True).run_once(
        limit=10, should_send=False)
    meals = store.meals_for_window(wid, confirmed_only=False)
    roti_rows = [m for m in meals
                 if {it["item"] for it in json.loads(m["items_json"])} >= {"roti", "dal"}]
    assert len(roti_rows) == 1
    assert roti_rows[0]["ts"].startswith("2026-09-12T08:00")


def test_intake_worker_same_thing_meal_inherits_and_backdates(seeded, store, cfg):
    # Patient forgot to log yesterday's meal (registered on an earlier day),
    # then says "i ate the same thing and the reading was 220" WITH a day
    # reference: the reading AND the inherited meal must both go to yesterday.
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    store.record_raw_received("+919000000001", "2 roti dal",
                              message_id="WAMID-MEAL-BASE-1",
                              ts="2026-09-11T13:00:00")
    IntakeWorker(store, cfg, send_func=lambda out: True).run_once(
        limit=10, should_send=False)
    store.record_raw_received(
        "+919000000001",
        "yea yesterday i forgot to tell but i ate the same thing and the reading was 220",
        message_id="WAMID-MEAL-SAME-1", ts="2026-09-13T07:52:00")
    IntakeWorker(store, cfg, send_func=lambda out: True).run_once(
        limit=10, should_send=False)

    readings = store.readings_for_window(wid)
    ri = [r for r in readings if abs(r["value"] - 220) < 0.5]
    assert len(ri) == 1 and ri[0]["ts"].startswith("2026-09-12")

    meals = store.meals_for_window(wid, confirmed_only=False)
    by_day = {m["ts"][:10]: {it["item"] for it in json.loads(m["items_json"])}
              for m in meals}
    assert by_day.get("2026-09-11") == {"roti", "dal"}      # original
    assert by_day.get("2026-09-12") == {"roti", "dal"}      # inherited copy
    assert "2026-09-13" not in by_day                        # NOT today
    assert not any("forgot to tell" in it.get("item", "")
                   for m in meals for it in json.loads(m["items_json"]))


def test_intake_worker_applies_tag_answer_to_latest_reading(seeded, store, cfg, intake):
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    # 'sugar 145' is registered (tag unknown), then the patient answers the tag
    # question with 'fasting' — that answer is consumed quietly at the webhook
    # and the dashboard AI applies it in place to the latest reading.
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "sugar 145"})
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "fasting"})
    intake(store, cfg)
    readings = [r for r in store.readings_for_window(wid)
                if r["status"] == "confirmed" and abs(r["value"] - 145) < 0.5]
    assert len(readings) == 1
    assert readings[0]["tag"] == "fasting"
    assert any(a["action"] == "reading_tagged" for a in store.audit_log())


def test_intake_resolves_ambiguous_reading_on_patient_choice(seeded, store, cfg):
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    store.record_raw_received("+919000000001", "pata nahi shayad 230 or 330",
                              message_id="AMB-RES-1")
    w = IntakeWorker(store, cfg, send_func=lambda out: True)
    w.run_once(limit=10, should_send=False)
    assert [r for r in store.readings_for_window(wid) if r["status"] == "pending"]
    # The patient picks the true value.
    sent = []
    store.record_raw_received("+919000000001", "230 hai",
                              message_id="AMB-RES-2")
    w2 = IntakeWorker(store, cfg, send_func=lambda o: (sent.append(o), True)[1])
    w2.run_once(limit=10, should_send=True, send_gap=0)
    after = store.readings_for_window(wid)
    assert not [r for r in after if r["status"] == "pending"]
    assert any(abs(r["value"] - 230) < 0.5 and r["status"] == "confirmed"
               for r in after)
    assert any("230" in o.body for o in sent)
    assert any(a["action"] == "reading_resolved" for a in store.audit_log())


def test_intake_asks_already_logged_and_honors_dup_answer(seeded, store, cfg, intake):
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "sugar 200"})
    intake(store, cfg)
    # No before/after context yet -> the reading is 'needs confirmation'.
    pending = [r for r in store.readings_for_window(wid)
               if r["status"] == "pending" and abs(r["value"] - 200) < 0.5]
    assert len(pending) == 1
    # 'fasting' resolves it to confirmed (with the before/after tag).
    sent = []
    store.record_raw_received("+919000000001", "fasting", message_id="TAG-A-1")
    IntakeWorker(store, cfg, send_func=lambda o: (sent.append(o), True)[1]).run_once(
        limit=10, should_send=True, send_gap=0)
    assert any("Logged sugar 200" in o.body and "Fasting" in o.body for o in sent)
    confirmed = [r for r in store.readings_for_window(wid)
                 if r["status"] == "confirmed" and abs(r["value"] - 200) < 0.5]
    assert len(confirmed) == 1
    assert confirmed[0]["tag"] == "fasting"
    # Same value again the same day -> ask "already logged — naya ya mistake?"
    sent = []
    store.record_raw_received("+919000000001", "200", message_id="DUP-Q-1")
    IntakeWorker(store, cfg, send_func=lambda o: (sent.append(o), True)[1]).run_once(
        limit=10, should_send=True, send_gap=0)
    assert any("already logged" in o.body for o in sent)
    confirmed = [r for r in store.readings_for_window(wid)
                 if r["status"] == "confirmed" and abs(r["value"] - 200) < 0.5]
    assert len(confirmed) == 1
    # 'mistake' -> nothing new is logged.
    store.record_raw_received("+919000000001", "mistake", message_id="DUP-A-SKIP")
    IntakeWorker(store, cfg, send_func=lambda o: True).run_once(
        limit=10, should_send=True, send_gap=0)
    confirmed = [r for r in store.readings_for_window(wid)
                 if r["status"] == "confirmed" and abs(r["value"] - 200) < 0.5]
    assert len(confirmed) == 1
    # 'naya' -> the blocked value is now logged as a new confirmed reading.
    store.record_raw_received("+919000000001", "naya", message_id="DUP-A-NEW")
    IntakeWorker(store, cfg, send_func=lambda o: True).run_once(
        limit=10, should_send=True, send_gap=0)
    confirmed = [r for r in store.readings_for_window(wid)
                 if r["status"] == "confirmed" and abs(r["value"] - 200) < 0.5]
    assert len(confirmed) == 2


def test_intake_registers_backdated_reading_from_explicit_words(seeded, store, cfg):
    from app.core.ai_worker import IntakeWorker
    from datetime import date, timedelta
    pid, wid = seeded
    store.record_raw_received(
        "+919000000001",
        "yesterday evening near 3pm the post eating sugar was 300",
        message_id="BACKDATE-1")
    IntakeWorker(store, cfg, send_func=lambda o: True).run_once(
        limit=10, should_send=False)
    readings = [r for r in store.readings_for_window(wid)
                if r["status"] == "confirmed" and abs(r["value"] - 300) < 0.5]
    assert len(readings) == 1
    want_day = (date.today() - timedelta(days=1)).isoformat()
    assert readings[0]["ts"].startswith(want_day + "T15:")
    assert readings[0]["tag"] == "postprandial"
    assert any("300" in a["detail"] for a in store.audit_log()
               if a["action"] == "reading_registered")


def test_daily_log_endpoint_groups_by_day_and_slot(tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.core.datamodel import Store
    from app.server.main import create_app
    db = str(tmp_path / "dailylog.db")
    store = Store(db)
    pid = store.add_patient("Daily Log", "DL-1", "+919876543210")
    wid = store.open_window(pid, "2026-09-01", "2026-09-14")
    phone = "+919876543210"
    store.add_reading(wid, phone, "patient", "fasting", 120,
                      ts="2026-09-10T08:00:00")
    store.add_reading(wid, phone, "patient", "postlunch", 150,
                      ts="2026-09-10T14:00:00")
    store.add_reading(wid, phone, "patient", "postdinner", 180,
                      ts="2026-09-10T20:30:00", status="pending",
                      candidates_json="[170,180]")
    store.propose_meal(wid, phone, "patient", "text",
                       [{"item": "roti", "genus": "wheat", "portion": "m",
                         "carbs": 24, "gi": "med"}], "m", 220, 24, "med", 0.9,
                       ts="2026-09-10T09:00:00")
    store.close()
    c = TestClient(create_app(cfg=Settings(db_path=db, whatsapp="simulator")))
    data = c.get(f"/api/v1/patients/{pid}/daily-log").json()
    assert data["window_id"] == wid
    assert len(data["days"]) == 1 and data["days"][0]["date"] == "2026-09-10"
    day = data["days"][0]
    assert len(day["readings"]) == 3
    labels = {r["slot_label"] for r in day["readings"]}
    assert "Morning" in labels and "Afternoon" in labels and "Evening" in labels
    assert any(r["status"] == "pending" and r["candidates"] == [170, 180]
               for r in day["readings"])
    assert len(day["meals"]) == 1 and day["meals"][0]["items"][0]["item"] == "roti"


def test_intake_tag_negation_never_applies_denied_tag(seeded, store, cfg):
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "sugar 150"})
    IntakeWorker(store, cfg, send_func=lambda o: True).run_once(
        limit=10, should_send=True, send_gap=0)
    # Patient claims fasting, then corrects it: the denied tag must never apply.
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "fasting"})
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "wo fasting nhi thi"})
    sent = []
    IntakeWorker(store, cfg, send_func=lambda o: (sent.append(o), True)[1]).run_once(
        limit=10, should_send=True, send_gap=0)
    rows = [r for r in store.readings_for_window(wid)
            if r["status"] == "confirmed" and abs(r["value"] - 150) < 0.5]
    assert len(rows) == 1
    assert rows[0]["tag"] != "fasting"
    assert any("khane se pehle" in o.body or "fasting" in o.body
               for o in sent)  # asked again, never mis-tagged


def test_intake_correction_updates_latest_reading_and_confirms(seeded, store, cfg):
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "sugar 180"})
    IntakeWorker(store, cfg, send_func=lambda o: True).run_once(
        limit=10, should_send=True, send_gap=0)
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "fasting"})
    IntakeWorker(store, cfg, send_func=lambda o: True).run_once(
        limit=10, should_send=True, send_gap=0)
    # "130 not 120" must edit the last reading from 180 to 130.
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "130 not 120"})
    sent = []
    IntakeWorker(store, cfg, send_func=lambda o: (sent.append(o), True)[1]).run_once(
        limit=10, should_send=True, send_gap=0)
    rows = [r for r in store.readings_for_window(wid)
            if r["status"] == "confirmed"]
    assert len(rows) == 1 and abs(rows[0]["value"] - 130) < 0.5
    assert rows[0]["tag"] == "fasting"
    assert any("Update ho gaya" in o.body and "130" in o.body for o in sent)
    assert any("180" in o.body for o in sent)  # old value echoed


def test_intake_backdates_reading_to_explicit_date(seeded, store, cfg):
    from app.core.ai_worker import IntakeWorker
    pid, wid = seeded
    _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                              "text": "14 july 3 baje post eating sugar 300"})
    IntakeWorker(store, cfg, send_func=lambda o: True).run_once(
        limit=10, should_send=False)
    rows = [r for r in store.readings_for_window(wid)
            if r["status"] == "confirmed" and abs(r["value"] - 300) < 0.5]
    assert len(rows) == 1
    assert rows[0]["ts"].startswith("2026-07-14T03:00")
    assert rows[0]["tag"] == "postprandial"


def test_daylog_crud_endpoints(tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.core.datamodel import Store
    from app.server.main import create_app
    db = str(tmp_path / "crud.db")
    store = Store(db)
    pid = store.add_patient("CRUD", "CRUD-1", "+919876543210")
    wid = store.open_window(pid, "2026-09-01", "2026-09-14")
    store.close()
    c = TestClient(create_app(cfg=Settings(db_path=db, whatsapp="simulator")))
    h = {"X-Aahaar-Key": "aahaar-2026"}
    # add a reading
    r = c.post(f"/api/v1/patients/{pid}/readings", headers=h,
               json={"value": 128, "tag": "fasting", "ts": "2026-09-12T07:05:00"})
    assert r.status_code == 200
    rid = r.json()["id"]
    # edit it
    r = c.put(f"/api/v1/patients/{pid}/readings/{rid}", headers=h,
              json={"value": 132, "tag": "pre"})
    assert r.status_code == 200
    # wrong key is rejected
    assert c.put(f"/api/v1/patients/{pid}/readings/{rid}",
                 json={"value": 5}).status_code == 403
    # add + delete a meal
    r = c.post(f"/api/v1/patients/{pid}/meals", headers=h,
               json={"items": [{"item": "dal"}], "ts": "2026-09-12T13:00:00"})
    mid = r.json()["id"]
    # delete the reading + meal
    assert c.delete(f"/api/v1/patients/{pid}/readings/{rid}", headers=h).status_code == 200
    assert c.delete(f"/api/v1/patients/{pid}/meals/{mid}", headers=h).status_code == 200
    store = Store(db)
    assert len(store.readings_for_window(wid)) == 0
    assert len(store.meals_for_window(wid)) == 0


def test_demo_reset_endpoint(tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.core.datamodel import Store
    from app.server.main import create_app
    db = str(tmp_path / "reset.db")
    store = Store(db)
    pid = store.add_patient("Reset", "RST-1", "+919876543210")
    wid = store.open_window(pid, "2026-09-01", "2026-09-14")
    store.add_reading(wid, "+919876543210", "patient", "fasting", 120,
                      ts="2026-09-10T08:00:00")
    store.propose_meal(wid, "+919876543210", "patient", "text",
                       [{"item": "roti"}], "m", 220, 24, "med", 0.9,
                       ts="2026-09-10T09:00:00")
    store.record_raw_received("+919876543210", "sugar 120", ts="2026-09-10T08:00:00")
    store.close()
    c = TestClient(create_app(cfg=Settings(db_path=db, whatsapp="simulator")))
    assert c.post(f"/api/v1/patients/{pid}/demo-reset").status_code == 403
    r = c.post(f"/api/v1/patients/{pid}/demo-reset",
               headers={"X-Aahaar-Key": "aahaar-2026"})
    assert r.status_code == 200
    store = Store(db)
    assert len(store.readings_for_window(wid)) == 0
    assert len(store.meals_for_window(wid)) == 0
    assert len(store.raw_inbound_log(wid)) == 0
    assert store.get_patient(pid) is not None  # patient survives


def test_webhook_never_runs_intake_llm(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.server.main import create_app
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    import app.core.intake_ai as intake_ai
    calls = {"n": 0}
    def boom(*a, **k):
        calls["n"] += 1
        return None
    monkeypatch.setattr(intake_ai, "analyze_intake", boom)
    monkeypatch.setattr(intake_ai, "_call_gemini_intake", boom)
    c = TestClient(create_app(cfg=Settings(db_path=str(tmp_path / "wipe.db"),
                                           whatsapp="simulator")))
    payload = {
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "contacts": [{"wa_id": "917439030190"}],
                    "messages": [{"from": "917439030190", "id": "WAMID-NOAI-1",
                                  "type": "text", "text": {"body": "sugar 140"}}],
                },
            }]
        }]
    }
    r = c.post("/api/v1/webhooks/whatsapp", json=payload)
    assert r.status_code == 200 and r.json()["processed"] == 1
    assert calls["n"] == 0, "webhook path must never invoke the intake LLM"


# ---- persistent webhook event counter ------------------------------------
def test_webhook_events_persisted_across_restarts(tmp_path):
    """Verify webhook events are stored in SQLite and survive a fresh Store open."""
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.core.datamodel import Store
    from app.server.main import create_app
    db = str(tmp_path / "wh_ev.db")
    s1 = Store(db)
    s1.close()
    c = TestClient(create_app(cfg=Settings(db_path=db, whatsapp="simulator",
                                           operator_key="aahaar-2026")))
    # 1) GET verify hits our handler (simulates Meta callback check)
    c.get("/api/v1/webhooks/whatsapp",
          params={"hub.mode": "subscribe",
                  "hub.verify_token": "aahaar-verify",
                  "hub.challenge": "abc123"})
    # 2) POST inbound (store-first path)
    payload = {
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "contacts": [{"wa_id": "919100000000"}],
                    "messages": [{"from": "919100000000", "id": "WAMID-EVP-1",
                                  "type": "text", "text": {"body": "fasting 105"}}],
                },
            }]
        }]
    }
    c.post("/api/v1/webhooks/whatsapp", json=payload)
    # Status endpoint must reflect DB-persisted events, not just in-memory
    st = c.get("/api/v1/debug/status").json()
    assert st["webhook_events_count"] >= 2, f"expected >=2 persisted events, got {st['webhook_events_count']}"
    last = st["last_webhook_event"]
    assert last is not None and last["event_type"] in ("GET_VERIFY", "POST_INBOUND")
    # Close and reopen a completely fresh Store on the same SQLite file
    c.close()
    s2 = Store(db)
    assert s2.webhook_event_count() >= 2, "events must survive a fresh Store open"
    rows = s2.recent_webhook_events(limit=10)
    types = [r["event_type"] for r in rows]
    assert "GET_VERIFY" in types and "POST_INBOUND" in types
    s2.close()
