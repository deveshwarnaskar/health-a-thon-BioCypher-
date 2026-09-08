"""Assemble everything a doctor report needs — numbers plus chart-ready series.

Rendering lives in the report package (build_charts / build_report). This module
only prepares the *content*, and it does so in a strictly descriptive voice.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from datetime import datetime
from typing import Optional

from ..config import Settings
from .datamodel import Store
from .metrics import compute_window_metrics
from .nutrition import KATORI_LABELS


def build_report_context(store: Store, cfg: Settings, window_id: int) -> dict:
    m = compute_window_metrics(store, cfg, window_id)
    patient = store.get_patient(m["patient_id"])
    cg = store.get_caregiver(m["patient_id"])
    window = store.get_window(window_id)

    # --- extra data pulled straight from the store ----------------------
    readings = store.readings_for_window(window_id)
    meals = store.meals_for_window(window_id, confirmed_only=True)

    glucose_by_tag: dict[str, list[float]] = {}
    for r in readings:
        glucose_by_tag.setdefault(r["tag"], []).append(r["value"])

    genus_counts: Counter = Counter()
    high_weekday = high_weekend = total_weekday = total_weekend = 0
    for mm in meals:
        high = mm["gi"] == "high"
        try:
            weekday = datetime.strptime(mm["ts"][:10], "%Y-%m-%d").weekday() < 5
        except ValueError:
            weekday = True
        if weekday:
            total_weekday += 1
            high_weekday += high
        else:
            total_weekend += 1
            high_weekend += high
        for it in json.loads(mm.get("items_json") or "[]"):
            genus_counts[it.get("genus", "?")] += 1

    tot_genus = max(1, sum(genus_counts.values()))
    top_genera = [(g, n, round(n / tot_genus * 100, 0))
                  for g, n in genus_counts.most_common(3)]

    weekday_highgi = round(high_weekday / total_weekday * 100, 1) if total_weekday else None
    weekend_highgi = round(high_weekend / total_weekend * 100, 1) if total_weekend else None

    series = m["series"]
    dates = [s["date"] for s in series]
    fpg = [s["fpg"] for s in series if s["fpg"] is not None]
    fpg_dates = [s["date"] for s in series if s["fpg"] is not None]
    pp_means = [round(sum(s["ppbg"]) / len(s["ppbg"]), 1) if s["ppbg"] else None
                for s in series]
    pp_means_dates = [s["date"] for s, v in zip(series, pp_means) if v is not None]

    ctx = {
        "product": {
            "name": "Aahaar",
            "subtitle": "Glycemic Context — assistive, non-diagnostic",
            "generated": datetime.now().strftime("%d %b %Y, %H:%M"),
        },
        "window_id": window_id,
        "patient_id": m["patient_id"],
        "window": m["window_dates"],
        "adherence_index": m["adherence_index"],
        "meals_count": m["meals_count"],
        "readings_count": m["readings_count"],
        "active_logging_days": m["active_logging_days"],
        "eligible_days": m["eligible_days"],
        "patient": {
            "name": m["patient_name"],
            "uh_id": m["uh_id"] or "—",
            "caregiver": (cg or {}).get("name", "—"),
            "caregiver_phone": (cg or {}).get("phone", "—"),
        },
        "glucose": {
            "mean_fpg": m["mean_fpg"],
            "mean_pre": m["mean_pre"],
            "mean_ppbg": m["mean_ppbg"],
            "weekday_ppbg": m["weekday_ppbg"],
            "weekend_ppbg": m["weekend_ppbg"],
            "weekend_ppbg_delta": m["weekend_ppbg_delta"],
            "weekday_highgi": weekday_highgi,
            "weekend_highgi": weekend_highgi,
            "target_low": cfg.glucose_low,
            "target_high": cfg.glucose_high,
        },
        "glucose_by_tag": glucose_by_tag,
        "top_genera": top_genera,
        "tir": m["tir"],
        "meals": {
            "high_gi_count": m["high_gi_count"],
            "high_gi_share": m["high_gi_share"],
            "carb_volatility": m["carb_volatility"],
            "portion_counts": _decorate(m["portion_counts"], KATORI_LABELS),
            "gi_counts": m["gi_counts"],
        },
        "avoid": {"count": m["avoid_count"], "items": m["avoid_items"]},
        "charts": {
            "dates": dates,
            "fpg": fpg_dates,
            "fpg_values": fpg,
            "ppbg": pp_means_dates,
            "ppbg_values": pp_means,
            "corridor_low": cfg.glucose_low,
            "corridor_high": cfg.glucose_high,
            "high_gi_share_daily": [s["high_gi_share"] for s in series],
            "weekends": [s["weekend"] for s in series],
            "correlation": m["correlation"],
        },
    }
    ctx["patterns"] = _patterns(ctx)
    return ctx


def _patterns(ctx: dict) -> list[tuple[str, str]]:
    glu = ctx["glucose"]
    mm = ctx["meals"]
    out = []
    if glu["weekend_ppbg"] and glu["weekday_ppbg"]:
        d = glu["weekend_ppbg"] - glu["weekday_ppbg"]
        word = "higher" if d > 0 else "lower"
        out.append(("Weekend PPBG excursion",
                    f"Mean postprandial glucose was {abs(d):.1f} mg/dL {word} on weekends "
                    f"({glu['weekend_ppbg']:.1f}) than on weekdays "
                    f"({glu['weekday_ppbg']:.1f}) in this window (observed)."))
    if mm["high_gi_share"] is not None:
        out.append(("High-GI meal presence",
                    f"High-GI items were logged in {mm['high_gi_share']:.1f}% of confirmed "
                    f"meals this window (reflective count)."))
    if mm["carb_volatility"] is not None:
        out.append(("Day-to-day carb variation",
                    f"Daily logged carb totals varied with a coefficient of "
                    f"{mm['carb_volatility']:.2f} (Carb Volatility Index) — a descriptive "
                    f"spread measure, not a risk score."))
    if ctx["avoid"]["count"]:
        names = ", ".join(ctx["avoid"]["items"])
        out.append(("Doctor-set avoid list",
                    f"Meals containing items on the doctor's avoid list ({names}) were logged "
                    f"{ctx['avoid']['count']} times — a reflective count only, no consequence "
                    f"implied."))
    out.append(("Logging adherence",
                f"{ctx['active_logging_days']} of {ctx['eligible_days']} eligible window days "
                f"had at least one logged meal photo or glucose reading "
                f"(Adherence Index {ctx['adherence_index']:g}%)."))
    return out[:4]


def _decorate(counts: dict, labels: dict) -> list[dict]:
    out = []
    for k in ("s", "m", "l"):
        n = counts.get(k, 0)
        out.append({"letter": k.upper(), "label": labels.get(k, ""), "count": n})
    return out


def latest_report_context(store: Store, cfg: Settings, patient_id: int) -> Optional[dict]:
    w = store.last_window_for(patient_id)
    if not w:
        return None
    return build_report_context(store, cfg, w["id"])