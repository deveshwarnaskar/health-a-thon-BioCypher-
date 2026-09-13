"""Descriptive metrics for one logging window.

Everything here is *descriptive* of what the patient/caregiver logged. There is
no prediction, no diagnosis and no recommendation. Numbers are computed from
confirmed meals + logged readings only.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Optional

from ..config import Settings
from .datamodel import Store
from .process import IngestService


def _day(ts: str) -> str:
    return (ts or "")[:10]


def _is_weekend(ts: str) -> bool:
    try:
        return datetime.strptime(ts[:10], "%Y-%m-%d").weekday() >= 5
    except ValueError:
        return False


_POST_TAGS = {"postprandial", "postbreakfast", "postlunch", "postdinner"}
_SLOT_TAG = {"postbreakfast": "postbreakfast", "postlunch": "postlunch",
             "postdinner": "postdinner"}
_READING_TYPE_BY_TAG = {
    "fasting": "fasting",
    "pre": "random",
    "postprandial": "postprandial",
    "postbreakfast": "postprandial",
    "postlunch": "postprandial",
    "postdinner": "postprandial",
    "random": "random",
    "post": "postprandial",
}


def _reading_type(r: dict) -> str:
    """Collapse every reading to the 3-type taxonomy: fasting | postprandial |
    random. Prefers the dedicated reading_type column; old rows and any unpaid
    tag values fall back through the tag mapping (default: random — a bare or
    uncontextualised reading is a random check, never an assumed 2-hour value)."""
    rt = str(r.get("reading_type") or "").strip()
    if rt in ("fasting", "postprandial", "random"):
        return rt
    return _READING_TYPE_BY_TAG.get(str(r.get("tag") or ""), "random")


def _hour_of(ts: str) -> Optional[int]:
    try:
        return int(ts[11:13])
    except (ValueError, IndexError):
        return None


def _slot_hour(h: Optional[int]) -> str:
    if h is None or h >= 16:
        return "postdinner"
    if h < 11:
        return "postbreakfast"
    return "postlunch"


def _meal_slot(meal_ts: str) -> str:
    return _slot_hour(_hour_of(meal_ts))


def _preceding_meal_slot(reading_ts: str, confirmed_meals: list[dict]) -> Optional[str]:
    """Slot of the nearest confirmed meal logged *before* the reading (within 4 h)."""
    try:
        rt = datetime.fromisoformat(reading_ts.replace("Z", ""))
    except ValueError:
        return None
    best: Optional[str] = None
    best_dt: Optional[datetime] = None
    for mm in confirmed_meals:
        try:
            mt = datetime.fromisoformat((mm["ts"] or "").replace("Z", ""))
        except ValueError:
            continue
        if mt > rt:
            continue
        if best_dt is None or mt > best_dt:
            best, best_dt = _meal_slot(mm["ts"]), mt
    if best is None or (rt - best_dt).total_seconds() > 4 * 3600:
        return None
    return best


def _slot_for(r: dict, confirmed_meals: list[dict]) -> str:
    tag = r.get("tag")
    if tag in _SLOT_TAG:
        return tag
    inferred = _preceding_meal_slot(r.get("ts") or "", confirmed_meals)
    if inferred:
        return inferred
    return _slot_hour(_hour_of(r.get("ts") or ""))


def compute_window_metrics(store: Store, cfg: Settings, window_id: int) -> dict:
    window = store.get_window(window_id)
    if not window:
        return {}
    meals = store.meals_for_window(window_id, confirmed_only=True)
    readings = [r for r in store.readings_for_window(window_id)
                if r.get("status", "confirmed") != "pending"]
    patient = store.get_patient(window["patient_id"])
    avoid = set(store.get_avoid_items(window["patient_id"]))
    dates = IngestService.window_dates(window)
    today = datetime.now().date()
    eligible = [d for d in dates if d <= today]

    # --- adherence ---------------------------------------------------
    active_days = {_day(m["ts"]) for m in meals} | {_day(r["ts"]) for r in readings}
    eligible_days = max(1, len(eligible))
    adherence = round(len(active_days) / eligible_days * 100, 1)

    # --- glucose -----------------------------------------------------
    # 3-type taxonomy: fasting | postprandial (2 hr) | random.
    tag_values: dict[str, list[float]] = defaultdict(list)
    by_day: dict[str, list[float]] = defaultdict(list)
    slot_by_reading: dict[int, str] = {}
    for r in readings:
        t = _reading_type(r)
        tag_values[t].append(r["value"])
        by_day[_day(r["ts"])].append(r["value"])
        if t == "postprandial":
            slot_by_reading[r["id"]] = _slot_for(r, meals)

    def mean(vals):
        return round(statistics.fmean(vals), 1) if vals else None

    mean_fpg = mean(tag_values.get("fasting", []))
    mean_random = mean(tag_values.get("random", []))

    post_vals: dict[str, list[float]] = {"postbreakfast": [], "postlunch": [], "postdinner": []}
    post_wkday: dict[str, list[float]] = {"postbreakfast": [], "postlunch": [], "postdinner": []}
    post_wkend: dict[str, list[float]] = {"postbreakfast": [], "postlunch": [], "postdinner": []}
    for r in readings:
        if _reading_type(r) != "postprandial":
            continue
        slot = slot_by_reading.get(r["id"]) or _slot_for(r, meals)
        post_vals[slot].append(r["value"])
        (post_wkend if _is_weekend(r["ts"]) else post_wkday)[slot].append(r["value"])

    all_pp = post_vals["postbreakfast"] + post_vals["postlunch"] + post_vals["postdinner"]
    mean_ppbg = mean(all_pp)

    pp_weekday = post_wkday["postbreakfast"] + post_wkday["postlunch"] + post_wkday["postdinner"]
    pp_weekend = post_wkend["postbreakfast"] + post_wkend["postlunch"] + post_wkend["postdinner"]
    wkday_ppbg = mean(pp_weekday)
    wkend_ppbg = mean(pp_weekend)

    slot_stats = {
        slot: {"count": len(post_vals[slot]), "mean": mean(post_vals[slot]),
               "weekday": mean(post_wkday[slot]), "weekend": mean(post_wkend[slot])}
        for slot in ("postbreakfast", "postlunch", "postdinner")
    }

    total = len(readings)
    n_in = sum(1 for r in readings if cfg.glucose_low <= r["value"] <= cfg.glucose_high)
    n_above = sum(1 for r in readings if r["value"] > cfg.glucose_high)
    n_below = sum(1 for r in readings if r["value"] < cfg.glucose_low)
    pct = lambda n: round(n / total * 100, 0) if total else 0
    tir = {"total": total, "in": pct(n_in), "above": pct(n_above), "below": pct(n_below),
           "low": cfg.glucose_low, "high": cfg.glucose_high}

    # --- meals / carbs ------------------------------------------------
    daily_carbs: dict[str, float] = defaultdict(float)
    high_gi_count = 0
    portion_counts: dict[str, int] = defaultdict(int)
    gi_counts: dict[str, int] = defaultdict(int)
    avoid_count = 0
    # Only meals that actually carry a recorded GI count towards the high-GI
    # share — rows logged without a GI (novel foods, pending) are skipped.
    gi_meals = [m for m in meals if m.get("gi")]
    for m in gi_meals:
        gi_counts[m["gi"] or "med"] += 1
    for m in meals:
        daily_carbs[_day(m["ts"])] += m["carbs"] or 0
        portion_counts[m["portion"] or "m"] += 1
        if m["gi"] == "high":
            high_gi_count += 1
        items = m.get("items_json") or "[]"
        if any(k in items for k in avoid):
            avoid_count += 1

    carb_vals = list(daily_carbs.values())
    if len(carb_vals) > 1 and statistics.mean(carb_vals) > 0:
        cv = statistics.pstdev(carb_vals) / statistics.mean(carb_vals)
        carb_volatility = round(cv, 2)
    else:
        carb_volatility = None

    high_gi_share = (round(high_gi_count / len(gi_meals) * 100, 1)
                     if gi_meals else None)

    # --- daily series (for charts) -------------------------------------
    series = []
    for d in dates:
        ds = d.isoformat()
        day_meals = [m for m in meals if _day(m["ts"]) == ds]
        day_gi = [m for m in day_meals if m.get("gi")]
        day_high = sum(1 for m in day_gi if m["gi"] == "high")
        def _slot_day(slot):
            return [r["value"] for r in readings
                    if _reading_type(r) == "postprandial" and _day(r["ts"]) == ds
                    and slot_by_reading.get(r["id"]) == slot]
        series.append({
            "date": ds,
            "weekend": d.weekday() >= 5,
            "fpg": next((r["value"] for r in readings if _reading_type(r) == "fasting" and _day(r["ts"]) == ds), None),
            "ppbg": [r["value"] for r in readings if _reading_type(r) == "postprandial" and _day(r["ts"]) == ds],
            "pb": _slot_day("postbreakfast"),
            "pl": _slot_day("postlunch"),
            "pd": _slot_day("postdinner"),
            "meals_today": len(day_meals),
            "high_gi_count": day_high,
            "high_gi_share": (round(day_high / len(day_gi) * 100, 0)
                                  if day_gi else None),
            "carbs": daily_carbs.get(ds, 0.0),
        })

    # --- correlation (daily high-GI share vs daily mean PPBG) ----------
    pairs = []
    for s in series:
        if s["ppbg"] and s["high_gi_share"]:
            pairs.append((float(s["high_gi_share"]), statistics.fmean(s["ppbg"])))
    corr = _pearson(pairs) if len(pairs) >= 3 else None

    return {
        "window_id": window_id,
        "patient_id": window["patient_id"],
        "patient_name": patient["name"] if patient else "",
        "uh_id": patient["uh_id"] if patient else "",
        "window_dates": {"start": window["start_date"], "end": window["end_date"]},
        "meals_count": len(meals),
        "readings_count": total,
        "active_logging_days": len(active_days),
        "eligible_days": eligible_days,
        "adherence_index": adherence,
        "mean_fpg": mean_fpg, "mean_random": mean_random, "mean_pre": mean_random,
        "mean_ppbg": mean_ppbg,
        "weekday_ppbg": wkday_ppbg, "weekend_ppbg": wkend_ppbg,
        "post_breakfast": slot_stats["postbreakfast"],
        "post_lunch": slot_stats["postlunch"],
        "post_dinner": slot_stats["postdinner"],
        "tir": tir,
        "high_gi_count": high_gi_count, "high_gi_share": high_gi_share,
        "carb_volatility": carb_volatility,
        "portion_counts": dict(portion_counts), "gi_counts": dict(gi_counts),
        "avoid_count": avoid_count, "avoid_items": sorted(avoid),
        "weekend_ppbg_delta": round((wkend_ppbg or 0) - (wkday_ppbg or 0), 1)
        if wkday_ppbg and wkend_ppbg else None,
        "fasting_fp": f"{datetime.now():%Y-%m-%d}",
        "correlation": corr,
        "series": series,
    }


def _pearson(pairs: list[tuple[float, float]]) -> Optional[float]:
    if not pairs:
        return None
    xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
    nx = len(xs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return round(sxy / math.sqrt(sxx * syy), 2)


def latest_metrics(store: Store, cfg: Settings, patient_id: int) -> Optional[dict]:
    w = store.last_window_for(patient_id)
    if not w:
        return None
    return compute_window_metrics(store, cfg, w["id"])