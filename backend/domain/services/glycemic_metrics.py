"""Glycemic analytics engine (Domain Service).

Accepts plain Python dicts so it can be called from any layer without coupling.
No database, no network, stdlib only (math, statistics, collections, datetime, typing).

Computes:
  - Time-in-Range (TIR: 70–180 mg/dL: in / above / below %)
  - Adherence Index (active days / elapsed days × 100)
  - Meal-slot PPBG (PB / PL / PD with weekday/weekend breakdown)
  - Carb Volatility Index (CVI = σ / μ of daily carbs)
  - Pearson r (daily high-GI share vs. postprandial glucose)

All outputs are descriptive — no diagnostic labels, no autonomous recommendations.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GLUCOSE_LOW = 70.0
GLUCOSE_HIGH = 180.0

_POST_TAGS = {"postprandial", "postbreakfast", "postlunch", "postdinner"}
_SLOT_TAG = {
    "postbreakfast": "postbreakfast",
    "postlunch": "postlunch",
    "postdinner": "postdinner",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _day(ts: str) -> str:
    return (ts or "")[:10]


def _is_weekend(ts: str) -> bool:
    try:
        return datetime.strptime(ts[:10], "%Y-%m-%d").weekday() >= 5
    except ValueError:
        return False


def _hour_of(ts: str) -> Optional[int]:
    try:
        return int(ts[11:13])
    except (ValueError, IndexError):
        return None


def _slot_by_hour(h: Optional[int]) -> str:
    if h is None or h >= 16:
        return "postdinner"
    if h < 11:
        return "postbreakfast"
    return "postlunch"


def _preceding_meal_slot(reading_ts: str, confirmed_meals: list[dict]) -> Optional[str]:
    """Slot of the nearest confirmed meal before the reading (within 4 h)."""
    try:
        rt = datetime.fromisoformat(reading_ts.replace("Z", ""))
    except ValueError:
        return None
    best: Optional[str] = None
    best_dt: Optional[datetime] = None
    for mm in confirmed_meals:
        m_ts = mm.get("recorded_at") or mm.get("ts") or ""
        try:
            mt = datetime.fromisoformat(str(m_ts).replace("Z", ""))
        except ValueError:
            continue
        if mt > rt:
            continue
        if best_dt is None or mt > best_dt:
            best_dt = mt
            best = _slot_by_hour(_hour_of(str(m_ts)))
    if best is None or best_dt is None:
        return None
    if (rt - best_dt).total_seconds() > 4 * 3600:
        return None
    return best


def _slot_for(r: dict, confirmed_meals: list[dict]) -> str:
    tag = r.get("tag") or ""
    if tag in _SLOT_TAG:
        return tag
    inferred = _preceding_meal_slot(r.get("taken_at") or r.get("ts") or "", confirmed_meals)
    if inferred:
        return inferred
    return _slot_by_hour(_hour_of(r.get("taken_at") or r.get("ts") or ""))


def _mean(vals: list[float]) -> Optional[float]:
    return round(statistics.fmean(vals), 1) if vals else None


def _pearson(pairs: list[tuple[float, float]]) -> Optional[float]:
    if len(pairs) < 3:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return round(sxy / math.sqrt(sxx * syy), 2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_window_metrics(
    readings: list[dict],
    meals: list[dict],
    window_days: int = 14,
    glucose_low: float = GLUCOSE_LOW,
    glucose_high: float = GLUCOSE_HIGH,
) -> dict:
    """Compute all clinical window metrics from plain Python dicts.

    Args:
        readings:    list of dicts with keys: value (float), tag (str),
                     taken_at (ISO str).
        meals:       list of dicts with keys: carbs_grams (float|None),
                     gi_category (str|None), recorded_at (ISO str),
                     confirmation (str) — only confirmed/corrected counted.
        window_days: number of elapsed assessment days.
        glucose_low: lower TIR boundary (default 70).
        glucose_high: upper TIR boundary (default 180).

    Returns a flat dict suitable for JSON serialisation and PDF rendering.
    """
    confirmed_meals = [
        m for m in meals
        if str(m.get("confirmation", "")).lower() in ("confirmed", "corrected")
    ]

    # ---- glucose --------------------------------------------------------
    tag_values: dict[str, list[float]] = defaultdict(list)
    by_day: dict[str, list[float]] = defaultdict(list)
    slot_by_reading: dict[int, str] = {}

    for idx, r in enumerate(readings):
        val = float(r.get("value") or r.get("value_mg_dl") or 0)
        ts = str(r.get("taken_at") or r.get("ts") or "")
        tag = str(r.get("tag") or "postprandial")
        tag_values[tag].append(val)
        by_day[_day(ts)].append(val)
        if tag in _POST_TAGS:
            slot_by_reading[idx] = _slot_for(r, confirmed_meals)

    total = len(readings)
    n_in = sum(1 for r in readings if glucose_low <= float(r.get("value") or r.get("value_mg_dl") or 0) <= glucose_high)
    n_above = sum(1 for r in readings if float(r.get("value") or r.get("value_mg_dl") or 0) > glucose_high)
    n_below = sum(1 for r in readings if float(r.get("value") or r.get("value_mg_dl") or 0) < glucose_low)

    def pct(n: int) -> float:
        return round(n / total * 100, 1) if total else 0.0

    # post-prandial slot breakdown
    post_vals: dict[str, list[float]] = {"postbreakfast": [], "postlunch": [], "postdinner": []}
    post_wkday: dict[str, list[float]] = {"postbreakfast": [], "postlunch": [], "postdinner": []}
    post_wkend: dict[str, list[float]] = {"postbreakfast": [], "postlunch": [], "postdinner": []}

    for idx, r in enumerate(readings):
        tag = str(r.get("tag") or "")
        if tag not in _POST_TAGS:
            continue
        val = float(r.get("value") or r.get("value_mg_dl") or 0)
        ts = str(r.get("taken_at") or r.get("ts") or "")
        slot = slot_by_reading.get(idx, _slot_by_hour(_hour_of(ts)))
        if slot not in post_vals:
            slot = "postdinner"
        post_vals[slot].append(val)
        (post_wkend if _is_weekend(ts) else post_wkday)[slot].append(val)

    all_pp = post_vals["postbreakfast"] + post_vals["postlunch"] + post_vals["postdinner"]
    pp_weekday = post_wkday["postbreakfast"] + post_wkday["postlunch"] + post_wkday["postdinner"]
    pp_weekend = post_wkend["postbreakfast"] + post_wkend["postlunch"] + post_wkend["postdinner"]

    wkday_ppbg = _mean(pp_weekday)
    wkend_ppbg = _mean(pp_weekend)

    # ---- adherence ------------------------------------------------------
    active_days: set[str] = set()
    for r in readings:
        ts = str(r.get("taken_at") or r.get("ts") or "")
        if ts:
            active_days.add(_day(ts))
    for m in confirmed_meals:
        ts = str(m.get("recorded_at") or m.get("ts") or "")
        if ts:
            active_days.add(_day(ts))

    eligible_days = max(1, window_days)
    adherence = round(len(active_days) / eligible_days * 100, 1)

    # ---- carbs / GI -----------------------------------------------------
    daily_carbs: dict[str, float] = defaultdict(float)
    high_gi_count = 0
    gi_counts: dict[str, int] = defaultdict(int)

    for m in confirmed_meals:
        ts = str(m.get("recorded_at") or m.get("ts") or "")
        carbs = float(m.get("carbs_grams") or 0.0)
        daily_carbs[_day(ts)] += carbs
        gi = str(m.get("gi_category") or m.get("gi") or "med")
        gi_counts[gi] += 1
        if gi == "high":
            high_gi_count += 1

    carb_vals = list(daily_carbs.values())
    if len(carb_vals) > 1 and statistics.mean(carb_vals) > 0:
        cvi: Optional[float] = round(
            statistics.pstdev(carb_vals) / statistics.mean(carb_vals), 2
        )
    else:
        cvi = None

    n_meals = len(confirmed_meals)
    high_gi_share = round(high_gi_count / n_meals * 100, 1) if n_meals else None

    # ---- daily series for charts / Pearson ------------------------------
    all_dates = sorted(active_days)
    series = []
    for ds in all_dates:
        day_meals = [m for m in confirmed_meals
                     if _day(str(m.get("recorded_at") or m.get("ts") or "")) == ds]
        day_readings = [r for r in readings
                        if _day(str(r.get("taken_at") or r.get("ts") or "")) == ds]
        day_high = sum(1 for m in day_meals if str(m.get("gi_category") or m.get("gi") or "") == "high")
        ppbg_day = [
            float(r.get("value") or r.get("value_mg_dl") or 0)
            for r in day_readings
            if str(r.get("tag") or "") in _POST_TAGS
        ]
        series.append({
            "date": ds,
            "weekend": _is_weekend(ds + "T00:00:00"),
            "fpg": next(
                (float(r.get("value") or r.get("value_mg_dl") or 0)
                 for r in day_readings if str(r.get("tag") or "") == "fasting"),
                None,
            ),
            "ppbg": ppbg_day,
            "meals_today": len(day_meals),
            "high_gi_count": day_high,
            "high_gi_share": round(day_high / len(day_meals) * 100, 1) if day_meals else 0.0,
            "carbs": daily_carbs.get(ds, 0.0),
        })

    # Pearson: daily high-GI share vs daily mean PPBG
    pairs = [
        (float(s["high_gi_share"]), statistics.fmean(s["ppbg"]))
        for s in series
        if s["ppbg"] and s["meals_today"] > 0
    ]
    pearson_r = _pearson(pairs)

    all_vals = [float(r.get("value") or r.get("value_mg_dl") or 0) for r in readings]

    return {
        "total_readings": total,
        "total_confirmed_meals": n_meals,
        "active_logging_days": len(active_days),
        "window_days": window_days,
        "adherence_index": adherence,
        # TIR
        "tir_in_range_pct": pct(n_in),
        "tir_above_range_pct": pct(n_above),
        "tir_below_range_pct": pct(n_below),
        "glucose_low": glucose_low,
        "glucose_high": glucose_high,
        # Glucose averages
        "mean_glucose": _mean(all_vals),
        "min_glucose": round(min(all_vals), 1) if all_vals else None,
        "max_glucose": round(max(all_vals), 1) if all_vals else None,
        "mean_fpg": _mean(tag_values.get("fasting", [])),
        "mean_ppbg": _mean(all_pp),
        "weekday_ppbg": wkday_ppbg,
        "weekend_ppbg": wkend_ppbg,
        "weekday_weekend_delta": (
            round((wkend_ppbg or 0) - (wkday_ppbg or 0), 1)
            if wkday_ppbg is not None and wkend_ppbg is not None
            else None
        ),
        # Slot breakdowns
        "slot_pb": {
            "count": len(post_vals["postbreakfast"]),
            "mean": _mean(post_vals["postbreakfast"]),
            "weekday": _mean(post_wkday["postbreakfast"]),
            "weekend": _mean(post_wkend["postbreakfast"]),
        },
        "slot_pl": {
            "count": len(post_vals["postlunch"]),
            "mean": _mean(post_vals["postlunch"]),
            "weekday": _mean(post_wkday["postlunch"]),
            "weekend": _mean(post_wkend["postlunch"]),
        },
        "slot_pd": {
            "count": len(post_vals["postdinner"]),
            "mean": _mean(post_vals["postdinner"]),
            "weekday": _mean(post_wkday["postdinner"]),
            "weekend": _mean(post_wkend["postdinner"]),
        },
        # Nutrition analytics (doctor-only)
        "high_gi_count": high_gi_count,
        "high_gi_share_pct": high_gi_share,
        "gi_counts": dict(gi_counts),
        "cvi": cvi,
        "pearson_r": pearson_r,
        # Daily series for charts
        "series": series,
    }


__all__ = ["compute_window_metrics", "GLUCOSE_LOW", "GLUCOSE_HIGH"]
