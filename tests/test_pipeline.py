"""Safety + behaviour invariants for the Aahaar pipeline.

These are the checks that keep the product OUT of the disqualified zone:
no diagnosis/prediction/advice wording, patient never sees carb/GI numbers,
unregistered numbers are refused, the confirm loop means only confirmed meals
feed the report, and one-caregiver bound per patient.
"""
from __future__ import annotations

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


def test_two_number_rule(seeded, store, cfg):
    pid, wid = seeded
    w = store.get_window(wid)
    # patient + one caregiver are fine
    for phone in ("+919000000001", "+919000000002"):
        replies = _handle(store, cfg, pid, {"sender_phone": phone, "kind": "text",
                                            "text": "fasting 120"})
        assert replies and "Logged fasting" in replies[0].body
    # appoint a new caregiver -> the previous binding is replaced, not stacked
    store.set_caregiver(pid, "+919000000009", "Someone Else")
    replies = _handle(store, cfg, pid, {"sender_phone": "+919000000009", "kind": "text",
                                        "text": "fasting 120"})
    assert replies and "Logged fasting" in replies[0].body
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
def test_tir_classification_70_180(seeded, store, cfg):
    pid, wid = seeded
    for vals in ([120, 150, 190, 60],):
        for v in vals:
            _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                                      "text": f"fasting {v}"})
    m = compute_window_metrics(store, cfg, wid)
    assert m["tir"]["total"] == 4
    assert m["tir"]["in"] == 50 and m["tir"]["above"] == 25 and m["tir"]["below"] == 25


def test_weekday_weekend_ppbg_split(seeded, store, cfg):
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


def test_post_slot_inferred_from_preceding_meal(seeded, store, cfg):
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
    m = compute_window_metrics(store, cfg, wid)
    assert m["post_breakfast"]["count"] == 1 and m["post_breakfast"]["mean"] == 158
    assert m["post_lunch"]["count"] == 0 and m["post_dinner"]["count"] == 0


def test_post_slot_stats_split_weekday_weekend(seeded, store, cfg):
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
    m = compute_window_metrics(store, cfg, wid)
    assert m["post_dinner"]["count"] == 2
    assert m["post_dinner"]["weekday"] == 150 and m["post_dinner"]["weekend"] == 200


def test_chart_context_has_three_slot_series(seeded, store, cfg):
    pid, wid = seeded
    from datetime import date
    day = date.fromisoformat(store.get_window(wid)["start_date"])
    d = day.isoformat()
    for txt, ts in (("post breakfast 150", "T10:00:00"),
                    ("post lunch 170", "T15:00:00"),
                    ("post dinner 200", "T21:00:00")):
        _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text",
                                  "text": txt, "ts": d + ts})
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


def test_typo_correction_and_talking_back_ai(seeded, store, cfg):
    pid, wid = seeded
    # Typo: 'sugr 14o' (letter 'o' instead of zero) -> recovered as 140 mg/dL
    r1 = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "sugr 14o"})
    assert r1 and "140" in r1[0].body

    # Typo: 'fastng 125'
    r2 = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "fastng 125"})
    assert r2 and "125" in r2[0].body

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

def test_prick_keyword_parsing(seeded, store, cfg):
    pid, wid = seeded
    # Patient sends 'prick 142' -> immediately recognized as blood sugar reading 142
    r1 = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "prick 142"})
    assert r1 and "142" in r1[0].body
    readings = store.readings_for_window(wid)
    assert any(rd["value"] == 142.0 for rd in readings)

    # Patient sends 'finger prick 135'
    r2 = _handle(store, cfg, pid, {"sender_phone": "+919000000001", "kind": "text", "text": "finger prick 135"})
    assert r2 and "135" in r2[0].body
    readings2 = store.readings_for_window(wid)
    assert any(rd["value"] == 135.0 for rd in readings2)


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

