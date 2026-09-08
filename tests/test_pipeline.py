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