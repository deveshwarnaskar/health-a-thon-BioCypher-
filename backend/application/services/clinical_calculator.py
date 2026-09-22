"""Clinical Glycemic Calculator (Pure Domain/Application Service).

Calculates standardized clinical metrics conforming to:
- ICMR / RSSDI Guidelines for Diabetes Management in India
- ADA / EASD International Consensus on Time in Range (TIR)
- AGP (Ambulatory Glucose Profile) Standards

Pure standard-library implementation. Never presumes medical diagnosis or actions.
Provides mathematical and statistical analysis for human clinician review.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Optional, Sequence


@dataclass(frozen=True)
class GlycemicMetricsResult:
    """Standardized glycemic metrics according to RSSDI/ADA standards."""

    total_readings: int
    mean_glucose_mg_dl: Optional[float]
    standard_deviation_mg_dl: Optional[float]
    coefficient_of_variation_pct: Optional[float]  # Target < 36%
    time_in_range_pct: Optional[float]  # 70 - 180 mg/dL (Target > 70%)
    time_below_range_pct: Optional[float]  # < 70 mg/dL (Target < 4%)
    time_below_range_level2_pct: Optional[float]  # < 54 mg/dL (Target < 1%)
    time_above_range_pct: Optional[float]  # > 180 mg/dL (Target < 25%)
    time_above_range_level2_pct: Optional[float]  # > 250 mg/dL (Target < 5%)
    estimated_hba1c_pct: Optional[float]  # eAG formula: (mean + 46.7) / 28.7
    glucose_management_indicator_pct: Optional[float]  # GMI = 3.31 + 0.02392 * mean
    fasting_mean_mg_dl: Optional[float]
    post_prandial_mean_mg_dl: Optional[float]
    hypo_events_count: int
    hyper_events_count: int
    dawn_phenomenon_suspected: bool
    variability_category: str  # "STABLE" (CV <= 36%) or "UNSTABLE" (CV > 36%)
    clinical_summary_note: str


def calculate_glycemic_metrics(
    readings: Sequence[dict[str, Any]],
) -> GlycemicMetricsResult:
    """Calculate standard clinical glycemic statistics from glucose readings.

    Each item in readings is expected to have:
    - 'value_mg_dl': int or float
    - 'taken_at': datetime or ISO string (optional)
    - 'tag': str e.g. 'fasting', 'postlunch', 'postdinner', 'random' (optional)
    """
    valid_values: list[float] = []
    fasting_values: list[float] = []
    pp_values: list[float] = []
    hypo_count = 0
    hyper_count = 0

    tir_count = 0  # 70 - 180
    tbr_count = 0  # < 70
    tbr_l2_count = 0  # < 54
    tar_count = 0  # > 180
    tar_l2_count = 0  # > 250

    morning_fasting_elevations: list[float] = []

    for r in readings:
        val = r.get("value_mg_dl")
        if val is None:
            val = r.get("value")
        if val is None:
            continue
        try:
            v = float(val)
        except (ValueError, TypeError):
            continue

        valid_values.append(v)

        if v < 70:
            hypo_count += 1
            tbr_count += 1
            if v < 54:
                tbr_l2_count += 1
        elif v <= 180:
            tir_count += 1
        else:
            hyper_count += 1
            tar_count += 1
            if v > 250:
                tar_l2_count += 1

        tag = str(r.get("tag") or "").upper()
        if "FAST" in tag:
            fasting_values.append(v)
            if v >= 130:
                morning_fasting_elevations.append(v)
        elif any(x in tag for x in ("POST", "PP", "AFTER")):
            pp_values.append(v)

    total = len(valid_values)
    if total == 0:
        return GlycemicMetricsResult(
            total_readings=0,
            mean_glucose_mg_dl=None,
            standard_deviation_mg_dl=None,
            coefficient_of_variation_pct=None,
            time_in_range_pct=None,
            time_below_range_pct=None,
            time_below_range_level2_pct=None,
            time_above_range_pct=None,
            time_above_range_level2_pct=None,
            estimated_hba1c_pct=None,
            glucose_management_indicator_pct=None,
            fasting_mean_mg_dl=None,
            post_prandial_mean_mg_dl=None,
            hypo_events_count=0,
            hyper_events_count=0,
            dawn_phenomenon_suspected=False,
            variability_category="INSUFFICIENT_DATA",
            clinical_summary_note="Paryapt data uplabdh nahi hai (No readings logged yet).",
        )

    mean = sum(valid_values) / total

    # Standard Deviation
    if total > 1:
        variance = sum((x - mean) ** 2 for x in valid_values) / (total - 1)
        sd = math.sqrt(variance)
    else:
        sd = 0.0

    cv = (sd / mean * 100.0) if mean > 0 else 0.0

    tir_pct = round((tir_count / total) * 100.0, 1)
    tbr_pct = round((tbr_count / total) * 100.0, 1)
    tbr_l2_pct = round((tbr_l2_count / total) * 100.0, 1)
    tar_pct = round((tar_count / total) * 100.0, 1)
    tar_l2_pct = round((tar_l2_count / total) * 100.0, 1)

    # eA1c: ADAG formula (Nathan et al., 2008)
    e_a1c = round((mean + 46.7) / 28.7, 1)
    # GMI: Bergenstal et al., 2018
    gmi = round(3.31 + 0.02392 * mean, 1)

    fasting_mean = round(sum(fasting_values) / len(fasting_values), 1) if fasting_values else None
    pp_mean = round(sum(pp_values) / len(pp_values), 1) if pp_values else None

    # Dawn phenomenon suspicion: multiple fasting readings > 130 mg/dL with no nocturnal hypoglycemia
    dawn_suspected = len(morning_fasting_elevations) >= 2 and tbr_count == 0

    variability_cat = "STABLE" if cv <= 36.0 else "HIGH_VARIABILITY"

    # Clinical note generation
    notes = []
    if tir_pct >= 70.0:
        notes.append(f"Optimal Time in Range ({tir_pct}% >= 70% target).")
    elif tir_pct >= 50.0:
        notes.append(f"Suboptimal Time in Range ({tir_pct}%, target >= 70%).")
    else:
        notes.append(f"Low Time in Range ({tir_pct}%). Glycemic control requires attention.")

    if tbr_pct > 4.0:
        notes.append(f"Hypoglycemia risk flagged: TBR is {tbr_pct}% (target < 4%).")

    if cv > 36.0:
        notes.append(f"High glycemic variability detected (CV: {cv:.1f}% > 36%).")
    else:
        notes.append(f"Stable glycemic variability (CV: {cv:.1f}% <= 36%).")

    if dawn_suspected:
        notes.append("Fasting pattern suggests possible Dawn Phenomenon (early morning elevation).")

    clinical_summary = " ".join(notes)

    return GlycemicMetricsResult(
        total_readings=total,
        mean_glucose_mg_dl=round(mean, 1),
        standard_deviation_mg_dl=round(sd, 1),
        coefficient_of_variation_pct=round(cv, 1),
        time_in_range_pct=tir_pct,
        time_below_range_pct=tbr_pct,
        time_below_range_level2_pct=tbr_l2_pct,
        time_above_range_pct=tar_pct,
        time_above_range_level2_pct=tar_l2_pct,
        estimated_hba1c_pct=e_a1c,
        glucose_management_indicator_pct=gmi,
        fasting_mean_mg_dl=fasting_mean,
        post_prandial_mean_mg_dl=pp_mean,
        hypo_events_count=hypo_count,
        hyper_events_count=hyper_count,
        dawn_phenomenon_suspected=dawn_suspected,
        variability_category=variability_cat,
        clinical_summary_note=clinical_summary,
    )
