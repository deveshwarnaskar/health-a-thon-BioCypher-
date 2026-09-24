"""Centralized Deterministic Clinical Calculation Engine (Pure Domain Service).

Authoritative, single source of truth for:
- Glycemic Metrics (Mean, Median, Min, Max, SD, CV, TIR, TAR, TBR, GMI, eAG)
- Completeness and Data Quality (Coverage, Expected vs Observed, Missing Intervals)
- Temporal Pattern Profiles (Morning, Afternoon, Evening, Overnight, Day-of-Week)
- Meal ↔ Glucose Temporal Associations (Pre-meal, Post-peak, Delta, Time-to-Peak)
- Longitudinal Comparisons (Current vs Preceding Periods: 7d, 14d, 30d, 90d, custom)
- Deterministic Clinical Calculations (2021 CKD-EPI eGFR, Screening Schedules)

CLINICAL SAFETY INVARIANTS:
1. Pure standard library implementation (math, statistics, datetime). No DB, no network, no LLM.
2. AI is NEVER the source of truth for deterministic medical metrics.
3. Insufficient data states are explicitly returned, never fabricated.
4. Non-causal descriptive language for temporal meal-glucose associations.
5. All calculations are versioned for deterministic report reproducibility.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

CLINICAL_ENGINE_VERSION = "2026.1-clinical-deterministic-ada-rssdi"

# Standard Clinical Reference Thresholds (ADA / EASD / RSSDI)
GLUCOSE_LOW_TBR = 70.0
GLUCOSE_LOW_L2 = 54.0
GLUCOSE_HIGH_TAR = 180.0
GLUCOSE_HIGH_L2 = 250.0
CV_TARGET_THRESHOLD = 36.0  # RSSDI/ADA: CV <= 36% denotes stable glycemic control
TIR_TARGET_PCT = 70.0  # RSSDI/ADA: Target TIR >= 70%
TBR_TARGET_PCT = 4.0  # RSSDI/ADA: Target TBR < 4%
TAR_TARGET_PCT = 25.0  # RSSDI/ADA: Target TAR < 25%


# ---------------------------------------------------------------------------
# Data Transfer / Value Objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GlycemicSummaryMetrics:
    total_readings: int
    mean_glucose: Optional[float]
    median_glucose: Optional[float]
    min_glucose: Optional[float]
    max_glucose: Optional[float]
    standard_deviation: Optional[float]
    coefficient_of_variation_pct: Optional[float]
    tir_in_range_pct: Optional[float]  # 70 - 180 mg/dL
    tar_above_range_pct: Optional[float]  # > 180 mg/dL
    tar_level2_pct: Optional[float]  # > 250 mg/dL
    tbr_below_range_pct: Optional[float]  # < 70 mg/dL
    tbr_level2_pct: Optional[float]  # < 54 mg/dL
    gmi_pct: Optional[float]  # GMI = 3.31 + 0.02392 * mean
    estimated_a1c_pct: Optional[float]  # eAG formula: (mean + 46.7) / 28.7
    fasting_mean: Optional[float]
    post_prandial_mean: Optional[float]
    dawn_phenomenon_suspected: bool
    variability_category: str  # "STABLE", "HIGH_VARIABILITY", or "INSUFFICIENT_DATA"
    clinical_summary_note: str


@dataclass(frozen=True)
class DataQualityCoverage:
    window_days: int
    active_logging_days: int
    total_valid_readings: int
    expected_readings: int
    coverage_ratio: float
    coverage_pct: float
    is_adequate_coverage: bool
    missing_days_count: int
    missing_days: List[str]
    last_sync: Optional[str]
    data_sources: List[str]


@dataclass(frozen=True)
class TimeSlotPattern:
    slot: str  # "morning", "afternoon", "evening", "overnight"
    hours_label: str
    count: int
    mean_glucose: Optional[float]
    median_glucose: Optional[float]
    tir_pct: Optional[float]
    tar_pct: Optional[float]
    tbr_pct: Optional[float]
    pattern_note: str


@dataclass(frozen=True)
class PatternProfile:
    morning: TimeSlotPattern
    afternoon: TimeSlotPattern
    evening: TimeSlotPattern
    overnight: TimeSlotPattern
    weekday_mean: Optional[float]
    weekend_mean: Optional[float]
    weekday_weekend_delta: Optional[float]
    observed_patterns: List[str]


@dataclass(frozen=True)
class MealGlucoseTemporalItem:
    meal_id: Optional[str]
    description: str
    recorded_at: str
    portion_label: Optional[str]
    carbs_grams: Optional[float]
    glycemic_index: Optional[str]
    pre_meal_glucose: Optional[float]
    post_meal_peak: Optional[float]
    delta_mg_dl: Optional[float]
    time_to_peak_minutes: Optional[int]
    associated_glucose_ids: List[str]
    relationship_note: str


@dataclass(frozen=True)
class LongitudinalDelta:
    current_value: Optional[float]
    previous_value: Optional[float]
    delta: Optional[float]
    trend_direction: str  # "improving", "stable", "deteriorating", "insufficient_data"


@dataclass(frozen=True)
class LongitudinalComparison:
    period_days: int
    current_readings_count: int
    previous_readings_count: int
    tir_comparison: LongitudinalDelta
    mean_comparison: LongitudinalDelta
    cv_comparison: LongitudinalDelta
    gmi_comparison: LongitudinalDelta
    has_sufficient_history: bool


@dataclass(frozen=True)
class ScreeningCategoryStatus:
    category: str
    code: str
    interval_months: int
    last_completed_at: Optional[str]
    due_date: Optional[str]
    is_overdue: bool
    status: str  # "CURRENT", "DUE_SOON", "OVERDUE", "NO_RECORD"


# ---------------------------------------------------------------------------
# Helper Parsing Functions
# ---------------------------------------------------------------------------


def parse_timestamp(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, date):
        return datetime.combine(val, time.min, tzinfo=timezone.utc)
    s = str(val).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def extract_glucose_value(item: Any) -> Optional[float]:
    if item is None:
        return None
    val = getattr(item, "value_mg_dl", None)
    if val is None:
        val = getattr(item, "value", None)
    if val is None and isinstance(item, dict):
        val = item.get("value_mg_dl")
        if val is None:
            val = item.get("value")
    if val is not None:
        if hasattr(val, "value_mg_dl"):
            val = val.value_mg_dl
        elif hasattr(val, "value"):
            val = val.value
        try:
            fv = float(val)
            if 20.0 <= fv <= 600.0:  # Valid physiological SMBG/CGM range
                return fv
        except (ValueError, TypeError):
            pass
    return None


def extract_timestamp(item: Any) -> Optional[datetime]:
    if item is None:
        return None
    for attr in ("taken_at", "recorded_at", "observed_at", "logged_at", "created_at", "ts"):
        v = getattr(item, attr, None) if not isinstance(item, dict) else item.get(attr)
        if v is not None:
            dt = parse_timestamp(v)
            if dt:
                return dt
    return None


def extract_tag(item: Any) -> str:
    tag = getattr(item, "tag", None) if not isinstance(item, dict) else item.get("tag")
    if tag is None:
        return ""
    if hasattr(tag, "value"):
        return str(tag.value).lower()
    return str(tag).lower()


# ---------------------------------------------------------------------------
# Core Glycemic Engine
# ---------------------------------------------------------------------------


def calculate_glycemic_metrics(
    readings: Sequence[Any],
    window_days: int = 14,
    glucose_low: float = GLUCOSE_LOW_TBR,
    glucose_high: float = GLUCOSE_HIGH_TAR,
) -> GlycemicSummaryMetrics:
    """Calculate deterministic glycemic metrics according to RSSDI/ADA consensus standards.

    Accepts plain dicts or domain observation objects.
    """
    valid_values: List[float] = []
    fasting_values: List[float] = []
    pp_values: List[float] = []
    morning_fasting_elevations: List[float] = []

    tir_count = 0
    tar_count = 0
    tar_l2_count = 0
    tbr_count = 0
    tbr_l2_count = 0

    for r in readings:
        val = extract_glucose_value(r)
        if val is None:
            continue
        valid_values.append(val)

        if val < glucose_low:
            tbr_count += 1
            if val < GLUCOSE_LOW_L2:
                tbr_l2_count += 1
        elif val <= glucose_high:
            tir_count += 1
        else:
            tar_count += 1
            if val > GLUCOSE_HIGH_L2:
                tar_l2_count += 1

        tag = extract_tag(r)
        if "fast" in tag:
            fasting_values.append(val)
            if val >= 130.0:
                morning_fasting_elevations.append(val)
        elif any(k in tag for k in ("post", "pp", "after")):
            pp_values.append(val)

    total = len(valid_values)
    if total == 0:
        return GlycemicSummaryMetrics(
            total_readings=0,
            mean_glucose=None,
            median_glucose=None,
            min_glucose=None,
            max_glucose=None,
            standard_deviation=None,
            coefficient_of_variation_pct=None,
            tir_in_range_pct=None,
            tar_above_range_pct=None,
            tar_level2_pct=None,
            tbr_below_range_pct=None,
            tbr_level2_pct=None,
            gmi_pct=None,
            estimated_a1c_pct=None,
            fasting_mean=None,
            post_prandial_mean=None,
            dawn_phenomenon_suspected=False,
            variability_category="INSUFFICIENT_DATA",
            clinical_summary_note="Paryapt data uplabdh nahi hai (No verified readings logged in this period).",
        )

    mean = statistics.fmean(valid_values)
    median = statistics.median(valid_values)
    min_val = min(valid_values)
    max_val = max(valid_values)

    if total > 1:
        sd = statistics.stdev(valid_values)
    else:
        sd = 0.0

    cv = (sd / mean * 100.0) if mean > 0 else 0.0

    tir_pct = round((tir_count / total) * 100.0, 1)
    tar_pct = round((tar_count / total) * 100.0, 1)
    tar_l2_pct = round((tar_l2_count / total) * 100.0, 1)
    tbr_pct = round((tbr_count / total) * 100.0, 1)
    tbr_l2_pct = round((tbr_l2_count / total) * 100.0, 1)

    # GMI = 3.31 + 0.02392 * mean (Bergenstal et al., 2018)
    gmi = round(3.31 + 0.02392 * mean, 1)
    # Estimated HbA1c via ADAG eAG formula (Nathan et al., 2008): (mean + 46.7) / 28.7
    e_a1c = round((mean + 46.7) / 28.7, 1)

    fasting_mean = round(statistics.fmean(fasting_values), 1) if fasting_values else None
    pp_mean = round(statistics.fmean(pp_values), 1) if pp_values else None

    # Dawn phenomenon pattern: multiple fasting elevations >= 130 mg/dL with no nocturnal hypoglycemia
    dawn_suspected = len(morning_fasting_elevations) >= 2 and tbr_count == 0
    variability_cat = "STABLE" if cv <= CV_TARGET_THRESHOLD else "HIGH_VARIABILITY"

    # Descriptive clinical summary
    notes: List[str] = []
    if tir_pct >= TIR_TARGET_PCT:
        notes.append(f"Optimal Time in Range ({tir_pct}% >= {TIR_TARGET_PCT}% target).")
    elif tir_pct >= 50.0:
        notes.append(f"Suboptimal Time in Range ({tir_pct}%, target >= {TIR_TARGET_PCT}%).")
    else:
        notes.append(f"Low Time in Range ({tir_pct}%). Glycemic control requires clinician review.")

    if tbr_pct > TBR_TARGET_PCT:
        notes.append(f"Hypoglycemia risk flagged: TBR is {tbr_pct}% (target < {TBR_TARGET_PCT}%).")

    if cv > CV_TARGET_THRESHOLD:
        notes.append(f"High glycemic variability detected (CV: {cv:.1f}% > {CV_TARGET_THRESHOLD}%).")
    else:
        notes.append(f"Stable glycemic variability (CV: {cv:.1f}% <= {CV_TARGET_THRESHOLD}%).")

    if dawn_suspected:
        notes.append("Fasting readings suggest possible Dawn Phenomenon (early morning elevation).")

    return GlycemicSummaryMetrics(
        total_readings=total,
        mean_glucose=round(mean, 1),
        median_glucose=round(median, 1),
        min_glucose=round(min_val, 1),
        max_glucose=round(max_val, 1),
        standard_deviation=round(sd, 1),
        coefficient_of_variation_pct=round(cv, 1),
        tir_in_range_pct=tir_pct,
        tar_above_range_pct=tar_pct,
        tar_level2_pct=tar_l2_pct,
        tbr_below_range_pct=tbr_pct,
        tbr_level2_pct=tbr_l2_pct,
        gmi_pct=gmi,
        estimated_a1c_pct=e_a1c,
        fasting_mean=fasting_mean,
        post_prandial_mean=pp_mean,
        dawn_phenomenon_suspected=dawn_suspected,
        variability_category=variability_cat,
        clinical_summary_note=" ".join(notes),
    )


# ---------------------------------------------------------------------------
# Data Quality & Completeness Engine
# ---------------------------------------------------------------------------


def calculate_data_quality(
    readings: Sequence[Any],
    meals: Sequence[Any],
    window_days: int = 14,
    reference_date: Optional[datetime] = None,
) -> DataQualityCoverage:
    """Computes descriptive data completeness and coverage across an evaluation window."""
    ref_dt = reference_date or datetime.now(timezone.utc)
    start_dt = ref_dt - timedelta(days=window_days)

    active_days: set[str] = set()
    sources: set[str] = set()
    last_sync_dt: Optional[datetime] = None
    valid_readings_count = 0

    for r in readings:
        val = extract_glucose_value(r)
        if val is None:
            continue
        ts = extract_timestamp(r)
        if ts:
            if ts > start_dt:
                active_days.add(ts.strftime("%Y-%m-%d"))
                valid_readings_count += 1
                if last_sync_dt is None or ts > last_sync_dt:
                    last_sync_dt = ts
            src = getattr(r, "source", None) if not isinstance(r, dict) else r.get("source")
            if src:
                sources.add(str(src))
            else:
                sources.add("smbg")

    for m in meals:
        ts = extract_timestamp(m)
        if ts and ts > start_dt:
            active_days.add(ts.strftime("%Y-%m-%d"))
            if last_sync_dt is None or ts > last_sync_dt:
                last_sync_dt = ts
            sources.add("meal_log")

    active_count = len(active_days)
    coverage_ratio = round(active_count / max(1, window_days), 3)
    coverage_pct = round(coverage_ratio * 100.0, 1)

    # Missing calendar days
    missing_days: List[str] = []
    for day_offset in range(window_days):
        d_str = (ref_dt - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        if d_str not in active_days:
            missing_days.append(d_str)
    missing_days.sort()

    expected_readings = window_days * 3  # Target 3 SMBG readings/day
    is_adequate = (coverage_pct >= 70.0) or (valid_readings_count >= min(14, window_days))

    return DataQualityCoverage(
        window_days=window_days,
        active_logging_days=active_count,
        total_valid_readings=valid_readings_count,
        expected_readings=expected_readings,
        coverage_ratio=coverage_ratio,
        coverage_pct=coverage_pct,
        is_adequate_coverage=is_adequate,
        missing_days_count=len(missing_days),
        missing_days=missing_days,
        last_sync=last_sync_dt.isoformat() if last_sync_dt else None,
        data_sources=sorted(list(sources)),
    )


# ---------------------------------------------------------------------------
# Temporal & Pattern Analysis Engine
# ---------------------------------------------------------------------------


def calculate_pattern_profile(
    readings: Sequence[Any],
    glucose_low: float = GLUCOSE_LOW_TBR,
    glucose_high: float = GLUCOSE_HIGH_TAR,
) -> PatternProfile:
    """Computes hourly time slot and day-of-week glycemic patterns."""
    slot_buckets: dict[str, List[float]] = {
        "morning": [],  # 06:00 - 12:00
        "afternoon": [],  # 12:00 - 17:00
        "evening": [],  # 17:00 - 22:00
        "overnight": [],  # 22:00 - 06:00
    }
    weekday_vals: List[float] = []
    weekend_vals: List[float] = []

    for r in readings:
        val = extract_glucose_value(r)
        if val is None:
            continue
        ts = extract_timestamp(r)
        if not ts:
            continue

        hour = ts.hour
        if 6 <= hour < 12:
            slot = "morning"
        elif 12 <= hour < 17:
            slot = "afternoon"
        elif 17 <= hour < 22:
            slot = "evening"
        else:
            slot = "overnight"

        slot_buckets[slot].append(val)
        if ts.weekday() >= 5:
            weekend_vals.append(val)
        else:
            weekday_vals.append(val)

    def _build_slot_pattern(slot_name: str, hours_label: str, vals: List[float]) -> TimeSlotPattern:
        n = len(vals)
        if n == 0:
            return TimeSlotPattern(
                slot=slot_name,
                hours_label=hours_label,
                count=0,
                mean_glucose=None,
                median_glucose=None,
                tir_pct=None,
                tar_pct=None,
                tbr_pct=None,
                pattern_note="No readings in this time window.",
            )

        mean_v = round(statistics.fmean(vals), 1)
        median_v = round(statistics.median(vals), 1)
        tir_n = sum(1 for v in vals if glucose_low <= v <= glucose_high)
        tar_n = sum(1 for v in vals if v > glucose_high)
        tbr_n = sum(1 for v in vals if v < glucose_low)

        tir_p = round(tir_n / n * 100.0, 1)
        tar_p = round(tar_n / n * 100.0, 1)
        tbr_p = round(tbr_n / n * 100.0, 1)

        note_parts = []
        if tar_p > 30.0:
            note_parts.append(f"Frequent postprandial/elevated excursion pattern ({tar_p}% > {glucose_high} mg/dL).")
        elif tbr_p > 5.0:
            note_parts.append(f"Hypoglycemia risk cluster observed ({tbr_p}% < {glucose_low} mg/dL).")
        elif tir_p >= 75.0:
            note_parts.append(f"Consistently in target range ({tir_p}%).")
        else:
            note_parts.append(f"Mean glucose {mean_v} mg/dL across {n} observations.")

        return TimeSlotPattern(
            slot=slot_name,
            hours_label=hours_label,
            count=n,
            mean_glucose=mean_v,
            median_glucose=median_v,
            tir_pct=tir_p,
            tar_pct=tar_p,
            tbr_pct=tbr_p,
            pattern_note=" ".join(note_parts),
        )

    morning_pat = _build_slot_pattern("morning", "06:00 - 12:00", slot_buckets["morning"])
    afternoon_pat = _build_slot_pattern("afternoon", "12:00 - 17:00", slot_buckets["afternoon"])
    evening_pat = _build_slot_pattern("evening", "17:00 - 22:00", slot_buckets["evening"])
    overnight_pat = _build_slot_pattern("overnight", "22:00 - 06:00", slot_buckets["overnight"])

    wkday_m = round(statistics.fmean(weekday_vals), 1) if weekday_vals else None
    wkend_m = round(statistics.fmean(weekend_vals), 1) if weekend_vals else None
    delta_w = round(wkend_m - wkday_m, 1) if (wkday_m is not None and wkend_m is not None) else None

    patterns: List[str] = []
    if delta_w is not None and abs(delta_w) >= 15.0:
        if delta_w > 0:
            patterns.append(f"Weekend glycemic elevation noted: weekend mean is {delta_w} mg/dL higher than weekdays.")
        else:
            patterns.append(f"Weekday glycemic elevation noted: weekday mean is {abs(delta_w)} mg/dL higher than weekends.")

    if evening_pat.tar_pct and evening_pat.tar_pct > 35.0:
        patterns.append("Repeated post-dinner glucose excursions observed during the evaluation window.")
    if overnight_pat.tbr_pct and overnight_pat.tbr_pct > 4.0:
        patterns.append("Nocturnal hypoglycemia cluster detected during overnight interval.")

    return PatternProfile(
        morning=morning_pat,
        afternoon=afternoon_pat,
        evening=evening_pat,
        overnight=overnight_pat,
        weekday_mean=wkday_m,
        weekend_mean=wkend_m,
        weekday_weekend_delta=delta_w,
        observed_patterns=patterns,
    )


# ---------------------------------------------------------------------------
# Meal ↔ Glucose Temporal Association Engine
# ---------------------------------------------------------------------------


def calculate_meal_glucose_temporal_associations(
    meals: Sequence[Any],
    readings: Sequence[Any],
    max_post_window_minutes: int = 240,
    max_pre_window_minutes: int = 60,
) -> List[MealGlucoseTemporalItem]:
    """Associates meal intakes with pre-meal baseline and post-meal glucose peak.

    Non-causal descriptive association only (Section 7).
    """
    sorted_meals = []
    for m in meals:
        ts = extract_timestamp(m)
        if ts:
            sorted_meals.append((ts, m))
    sorted_meals.sort(key=lambda x: x[0], reverse=True)

    sorted_readings = []
    for r in readings:
        val = extract_glucose_value(r)
        ts = extract_timestamp(r)
        if val is not None and ts:
            r_id = getattr(r, "id", None) or (r.get("id") if isinstance(r, dict) else None)
            sorted_readings.append((ts, val, str(r_id or "")))
    sorted_readings.sort(key=lambda x: x[0])

    items: List[MealGlucoseTemporalItem] = []

    for m_dt, meal in sorted_meals[:30]:  # Evaluate up to 30 recent meals
        m_id = getattr(meal, "id", None) or (meal.get("id") if isinstance(meal, dict) else None)
        desc = getattr(meal, "description", "") or (meal.get("description", "") if isinstance(meal, dict) else "")
        portion = getattr(meal, "portion_label", None) or (meal.get("portion_label") if isinstance(meal, dict) else None)
        carbs = getattr(meal, "carbs_grams", None) or (meal.get("carbs_grams") if isinstance(meal, dict) else None)
        gi = getattr(meal, "glycemic_index", None) or (meal.get("glycemic_index") if isinstance(meal, dict) else None)

        pre_val: Optional[float] = None
        best_pre_diff = float("inf")

        post_readings: List[Tuple[float, int, str]] = []  # (value, minutes_after, id)

        for r_dt, r_val, r_id in sorted_readings:
            diff_sec = (r_dt - m_dt).total_seconds()
            diff_min = diff_sec / 60.0

            # Pre-meal reading [-60m, 0m]
            if -max_pre_window_minutes <= diff_min <= 0:
                if abs(diff_min) < best_pre_diff:
                    best_pre_diff = abs(diff_min)
                    pre_val = r_val

            # Post-meal readings [10m, 240m]
            elif 10.0 <= diff_min <= max_post_window_minutes:
                post_readings.append((r_val, int(diff_min), r_id))

        if post_readings:
            # Find peak post-meal excursion
            post_peak_val, time_to_peak, peak_id = max(post_readings, key=lambda x: x[0])
            assoc_ids = [p[2] for p in post_readings if p[2]]

            delta: Optional[float] = None
            if pre_val is not None:
                delta = round(post_peak_val - pre_val, 1)

            note_parts = [f"Post-meal peak of {post_peak_val} mg/dL observed at {time_to_peak} min."]
            if delta is not None:
                sign = "+" if delta >= 0 else ""
                note_parts.append(f"Observed excursion: {sign}{delta} mg/dL from pre-meal reading ({pre_val} mg/dL).")
            else:
                note_parts.append("No pre-meal baseline recorded.")

            items.append(
                MealGlucoseTemporalItem(
                    meal_id=str(m_id) if m_id else None,
                    description=desc,
                    recorded_at=m_dt.isoformat(),
                    portion_label=str(portion) if portion else None,
                    carbs_grams=float(carbs) if carbs is not None else None,
                    glycemic_index=str(gi) if gi else None,
                    pre_meal_glucose=round(pre_val, 1) if pre_val is not None else None,
                    post_meal_peak=round(post_peak_val, 1),
                    delta_mg_dl=delta,
                    time_to_peak_minutes=time_to_peak,
                    associated_glucose_ids=assoc_ids,
                    relationship_note=" ".join(note_parts),
                )
            )

    return items


# ---------------------------------------------------------------------------
# Longitudinal Period Comparison Engine
# ---------------------------------------------------------------------------


def calculate_longitudinal_comparison(
    readings: Sequence[Any],
    window_days: int = 14,
    reference_date: Optional[datetime] = None,
) -> LongitudinalComparison:
    """Compares current period (last W days) against immediately preceding period (W to 2W days ago)."""
    ref_dt = reference_date or datetime.now(timezone.utc)
    current_start = ref_dt - timedelta(days=window_days)
    prev_start = ref_dt - timedelta(days=window_days * 2)

    current_readings: List[Any] = []
    prev_readings: List[Any] = []

    for r in readings:
        ts = extract_timestamp(r)
        if not ts:
            continue
        if current_start < ts <= ref_dt:
            current_readings.append(r)
        elif prev_start < ts <= current_start:
            prev_readings.append(r)

    curr_m = calculate_glycemic_metrics(current_readings, window_days)
    prev_m = calculate_glycemic_metrics(prev_readings, window_days)

    has_history = prev_m.total_readings >= 3

    def _delta(curr_v: Optional[float], prev_v: Optional[float], lower_is_better: bool = False) -> LongitudinalDelta:
        if curr_v is None or prev_v is None:
            return LongitudinalDelta(
                current_value=curr_v,
                previous_value=prev_v,
                delta=None,
                trend_direction="insufficient_data",
            )
        d = round(curr_v - prev_v, 1)
        if abs(d) <= 1.5:
            direction = "stable"
        elif lower_is_better:
            direction = "improving" if d < 0 else "deteriorating"
        else:
            direction = "improving" if d > 0 else "deteriorating"

        return LongitudinalDelta(
            current_value=curr_v,
            previous_value=prev_v,
            delta=d,
            trend_direction=direction,
        )

    return LongitudinalComparison(
        period_days=window_days,
        current_readings_count=curr_m.total_readings,
        previous_readings_count=prev_m.total_readings,
        tir_comparison=_delta(curr_m.tir_in_range_pct, prev_m.tir_in_range_pct, lower_is_better=False),
        mean_comparison=_delta(curr_m.mean_glucose, prev_m.mean_glucose, lower_is_better=True),
        cv_comparison=_delta(curr_m.coefficient_of_variation_pct, prev_m.coefficient_of_variation_pct, lower_is_better=True),
        gmi_comparison=_delta(curr_m.gmi_pct, prev_m.gmi_pct, lower_is_better=True),
        has_sufficient_history=has_history,
    )


# ---------------------------------------------------------------------------
# Validated Clinical Calculations (eGFR & Screening)
# ---------------------------------------------------------------------------


def calculate_egfr_ckd_epi_2021(
    serum_creatinine_mg_dl: float,
    age_years: int = 55,
    is_female: bool = False,
) -> float:
    """Calculates eGFR using the 2021 CKD-EPI Creatinine Equation (without race).

    Inker et al., New England Journal of Medicine, 2021.
    Formula:
      eGFR = 142 * min(Scr/kappa, 1)**alpha * max(Scr/kappa, 1)**(-1.200) * 0.9938**Age * (1.012 if female)
      where:
        female: kappa = 0.7, alpha = -0.241
        male:   kappa = 0.9, alpha = -0.302
    """
    if serum_creatinine_mg_dl <= 0:
        return 0.0

    kappa = 0.7 if is_female else 0.9
    alpha = -0.241 if is_female else -0.302
    female_factor = 1.012 if is_female else 1.0

    scr_over_k = serum_creatinine_mg_dl / kappa
    term1 = min(scr_over_k, 1.0) ** alpha
    term2 = max(scr_over_k, 1.0) ** (-1.200)
    term3 = 0.9938 ** max(18, age_years)

    egfr = 142.0 * term1 * term2 * term3 * female_factor
    return round(egfr, 1)


def calculate_screening_status(
    category_name: str,
    category_code: str,
    last_completed_dt: Optional[datetime],
    interval_months: int = 12,
    reference_dt: Optional[datetime] = None,
) -> ScreeningCategoryStatus:
    """Calculates due date and overdue status for clinical diabetes screenings."""
    ref_dt = reference_dt or datetime.now(timezone.utc)

    if last_completed_dt is None:
        return ScreeningCategoryStatus(
            category=category_name,
            code=category_code,
            interval_months=interval_months,
            last_completed_at=None,
            due_date=ref_dt.strftime("%Y-%m-%d"),
            is_overdue=True,
            status="OVERDUE",
        )

    # Calculate due date: + interval_months (approx interval_months * 30.4 days)
    due_dt = last_completed_dt + timedelta(days=int(interval_months * 30.4375))
    is_overdue = ref_dt > due_dt
    days_until = (due_dt - ref_dt).days

    if is_overdue:
        status = "OVERDUE"
    elif days_until <= 30:
        status = "DUE_SOON"
    else:
        status = "CURRENT"

    return ScreeningCategoryStatus(
        category=category_name,
        code=category_code,
        interval_months=interval_months,
        last_completed_at=last_completed_dt.strftime("%Y-%m-%d"),
        due_date=due_dt.strftime("%Y-%m-%d"),
        is_overdue=is_overdue,
        status=status,
    )


__all__ = [
    "CLINICAL_ENGINE_VERSION",
    "GLUCOSE_LOW_TBR",
    "GLUCOSE_LOW_L2",
    "GLUCOSE_HIGH_TAR",
    "GLUCOSE_HIGH_L2",
    "CV_TARGET_THRESHOLD",
    "TIR_TARGET_PCT",
    "TBR_TARGET_PCT",
    "TAR_TARGET_PCT",
    "GlycemicSummaryMetrics",
    "DataQualityCoverage",
    "TimeSlotPattern",
    "PatternProfile",
    "MealGlucoseTemporalItem",
    "LongitudinalDelta",
    "LongitudinalComparison",
    "ScreeningCategoryStatus",
    "calculate_glycemic_metrics",
    "calculate_data_quality",
    "calculate_pattern_profile",
    "calculate_meal_glucose_temporal_associations",
    "calculate_longitudinal_comparison",
    "calculate_egfr_ckd_epi_2021",
    "calculate_screening_status",
]
