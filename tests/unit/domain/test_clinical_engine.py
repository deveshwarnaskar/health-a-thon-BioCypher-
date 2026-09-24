"""Unit tests for the centralized deterministic clinical calculation engine.

Validates:
- Glycemic metrics (Mean, Median, Min, Max, SD, CV, TIR, TAR, TBR, GMI, eAG)
- Completeness and data quality coverage
- Hourly time-slot and weekday/weekend temporal pattern profiles
- Meal ↔ Glucose temporal associations
- Longitudinal period comparisons (current vs preceding)
- 2021 CKD-EPI eGFR calculation
- Complication screening scheduling (CURRENT, DUE_SOON, OVERDUE)
- Clinical safety invariants and edge case tolerance
"""

from datetime import datetime, timedelta, timezone
import pytest

from backend.domain.services.clinical_engine import (
    CLINICAL_ENGINE_VERSION,
    GLUCOSE_HIGH_L2,
    GLUCOSE_HIGH_TAR,
    GLUCOSE_LOW_L2,
    GLUCOSE_LOW_TBR,
    calculate_data_quality,
    calculate_egfr_ckd_epi_2021,
    calculate_glycemic_metrics,
    calculate_longitudinal_comparison,
    calculate_meal_glucose_temporal_associations,
    calculate_pattern_profile,
    calculate_screening_status,
)


class MockObservation:
    """Helper mock matching domain or DTO observation structures."""

    def __init__(self, value: float, dt: datetime, tag: str = "", obs_id: str = "obs-1", source: str = "smbg"):
        self.id = obs_id
        self.value_mg_dl = value
        self.recorded_at = dt
        self.tag = tag
        self.source = source


class MockMeal:
    """Helper mock matching domain meal structures."""

    def __init__(self, meal_id: str, desc: str, dt: datetime, portion: str = "1 bowl", carbs: float = 45.0, gi: str = "MEDIUM"):
        self.id = meal_id
        self.description = desc
        self.recorded_at = dt
        self.portion_label = portion
        self.carbs_grams = carbs
        self.glycemic_index = gi


# ==============================================================================
# 1. Glycemic Metrics Tests
# ==============================================================================


def test_glycemic_metrics_empty_readings():
    metrics = calculate_glycemic_metrics([])
    assert metrics.total_readings == 0
    assert metrics.mean_glucose is None
    assert metrics.median_glucose is None
    assert metrics.standard_deviation is None
    assert metrics.coefficient_of_variation_pct is None
    assert metrics.tir_in_range_pct is None
    assert metrics.gmi_pct is None
    assert metrics.estimated_a1c_pct is None
    assert metrics.variability_category == "INSUFFICIENT_DATA"
    assert "Paryapt data uplabdh nahi hai" in metrics.clinical_summary_note


def test_glycemic_metrics_single_reading():
    reading = {"value_mg_dl": 120.0, "recorded_at": "2026-09-20T08:00:00Z"}
    metrics = calculate_glycemic_metrics([reading])
    assert metrics.total_readings == 1
    assert metrics.mean_glucose == 120.0
    assert metrics.median_glucose == 120.0
    assert metrics.standard_deviation == 0.0
    assert metrics.coefficient_of_variation_pct == 0.0
    assert metrics.tir_in_range_pct == 100.0
    assert metrics.tar_above_range_pct == 0.0
    assert metrics.tbr_below_range_pct == 0.0
    assert metrics.variability_category == "STABLE"


def test_glycemic_metrics_known_distribution():
    # Readings: 60 (TBR L1), 100 (TIR), 140 (TIR), 200 (TAR L1), 260 (TAR L2)
    readings = [
        {"value": 60.0, "tag": "fasting"},
        {"value": 100.0, "tag": "fasting"},
        {"value": 140.0, "tag": "post_meal"},
        {"value": 200.0, "tag": "post_meal"},
        {"value": 260.0, "tag": "random"},
    ]
    metrics = calculate_glycemic_metrics(readings)

    assert metrics.total_readings == 5
    assert metrics.min_glucose == 60.0
    assert metrics.max_glucose == 260.0
    # Mean: (60+100+140+200+260)/5 = 760/5 = 152.0
    assert metrics.mean_glucose == 152.0
    # Median: 140.0
    assert metrics.median_glucose == 140.0

    # TIR (70-180): 100, 140 -> 2/5 = 40.0%
    assert metrics.tir_in_range_pct == 40.0
    # TAR (>180): 200, 260 -> 2/5 = 40.0%
    assert metrics.tar_above_range_pct == 40.0
    # TAR L2 (>250): 260 -> 1/5 = 20.0%
    assert metrics.tar_level2_pct == 20.0
    # TBR (<70): 60 -> 1/5 = 20.0%
    assert metrics.tbr_below_range_pct == 20.0
    # TBR L2 (<54): 0 -> 0.0%
    assert metrics.tbr_level2_pct == 0.0

    # GMI = 3.31 + 0.02392 * 152 = 3.31 + 3.63584 = 6.9%
    assert metrics.gmi_pct == pytest.approx(6.9, abs=0.1)
    # eAG = (152 + 46.7) / 28.7 = 198.7 / 28.7 = 6.9%
    assert metrics.estimated_a1c_pct == pytest.approx(6.9, abs=0.1)

    # Fasting mean: (60 + 100) / 2 = 80.0
    assert metrics.fasting_mean == 80.0
    # Post-prandial mean: (140 + 200) / 2 = 170.0
    assert metrics.post_prandial_mean == 170.0


def test_glycemic_metrics_cv_and_variability():
    # Low variability dataset (CV <= 36%)
    stable_readings = [{"value": v} for v in [110, 115, 112, 118, 114]]
    stable_metrics = calculate_glycemic_metrics(stable_readings)
    assert stable_metrics.variability_category == "STABLE"
    assert stable_metrics.coefficient_of_variation_pct < 36.0

    # High variability dataset (CV > 36%)
    volatile_readings = [{"value": v} for v in [50, 240, 65, 300, 80]]
    volatile_metrics = calculate_glycemic_metrics(volatile_readings)
    assert volatile_metrics.variability_category == "HIGH_VARIABILITY"
    assert volatile_metrics.coefficient_of_variation_pct > 36.0


def test_glycemic_metrics_dawn_phenomenon():
    # >= 2 fasting elevations >= 130 mg/dL with zero TBR readings
    readings = [
        {"value": 135.0, "tag": "fasting"},
        {"value": 142.0, "tag": "fasting"},
        {"value": 120.0, "tag": "post_meal"},
    ]
    metrics = calculate_glycemic_metrics(readings)
    assert metrics.dawn_phenomenon_suspected is True
    assert "Dawn Phenomenon" in metrics.clinical_summary_note

    # With a low reading, dawn phenomenon should NOT be flagged
    readings_with_hypo = readings + [{"value": 62.0, "tag": "fasting"}]
    metrics_hypo = calculate_glycemic_metrics(readings_with_hypo)
    assert metrics_hypo.dawn_phenomenon_suspected is False


# ==============================================================================
# 2. Data Quality & Completeness Tests
# ==============================================================================


def test_data_quality_coverage():
    now = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)
    # Logged on 10 distinct days in a 14-day window
    readings = [
        MockObservation(110.0, now - timedelta(days=i), obs_id=f"r-{i}")
        for i in range(10)
    ]
    meals = [
        MockMeal(f"m-{i}", "Dal Roti", now - timedelta(days=i))
        for i in range(5)
    ]

    quality = calculate_data_quality(readings, meals, window_days=14, reference_date=now)
    assert quality.window_days == 14
    assert quality.active_logging_days == 10
    assert quality.total_valid_readings == 10
    assert quality.expected_readings == 42  # 14 * 3
    assert quality.coverage_pct == pytest.approx(71.4, abs=0.1)
    assert quality.is_adequate_coverage is True
    assert quality.missing_days_count == 4
    assert len(quality.missing_days) == 4
    assert quality.last_sync is not None
    assert "smbg" in quality.data_sources
    assert "meal_log" in quality.data_sources


def test_data_quality_zero_coverage():
    now = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)
    quality = calculate_data_quality([], [], window_days=7, reference_date=now)
    assert quality.active_logging_days == 0
    assert quality.total_valid_readings == 0
    assert quality.coverage_pct == 0.0
    assert quality.is_adequate_coverage is False
    assert quality.missing_days_count == 7


# ==============================================================================
# 3. Temporal & Pattern Analysis Tests
# ==============================================================================


def test_pattern_profile_hourly_slots():
    # Morning: 08:00 (100 mg/dL)
    # Afternoon: 14:00 (130 mg/dL)
    # Evening: 20:00 (220 mg/dL - elevated)
    # Overnight: 03:00 (65 mg/dL - low)
    base = datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)  # Tuesday (weekday)
    readings = [
        MockObservation(100.0, base.replace(hour=8)),
        MockObservation(130.0, base.replace(hour=14)),
        MockObservation(220.0, base.replace(hour=20)),
        MockObservation(65.0, base.replace(hour=3)),
    ]

    profile = calculate_pattern_profile(readings)

    assert profile.morning.count == 1
    assert profile.morning.mean_glucose == 100.0
    assert profile.morning.tir_pct == 100.0

    assert profile.afternoon.count == 1
    assert profile.afternoon.mean_glucose == 130.0

    assert profile.evening.count == 1
    assert profile.evening.mean_glucose == 220.0
    assert profile.evening.tar_pct == 100.0

    assert profile.overnight.count == 1
    assert profile.overnight.mean_glucose == 65.0
    assert profile.overnight.tbr_pct == 100.0

    # Evening has TAR > 35% -> post-dinner excursion detected
    assert any("post-dinner" in p.lower() for p in profile.observed_patterns)
    # Overnight has TBR > 4% -> nocturnal hypoglycemia detected
    assert any("nocturnal" in p.lower() for p in profile.observed_patterns)


def test_pattern_profile_weekday_weekend_delta():
    # Weekday readings: Tuesday, Wednesday at 110 mg/dL
    # Weekend readings: Saturday, Sunday at 145 mg/dL (delta = +35 mg/dL >= 15 threshold)
    tuesday = datetime(2026, 9, 22, 10, 0, 0, tzinfo=timezone.utc)
    saturday = datetime(2026, 9, 26, 10, 0, 0, tzinfo=timezone.utc)

    readings = [
        MockObservation(110.0, tuesday),
        MockObservation(145.0, saturday),
    ]
    profile = calculate_pattern_profile(readings)
    assert profile.weekday_mean == 110.0
    assert profile.weekend_mean == 145.0
    assert profile.weekday_weekend_delta == 35.0
    assert any("weekend glycemic elevation" in p.lower() for p in profile.observed_patterns)


# ==============================================================================
# 4. Meal ↔ Glucose Temporal Associations Tests
# ==============================================================================


def test_meal_glucose_temporal_associations():
    meal_time = datetime(2026, 9, 24, 13, 0, 0, tzinfo=timezone.utc)
    meal = MockMeal("meal-1", "Katori Rice and Dal", meal_time, portion="1 large katori", carbs=65.0)

    # Pre-meal reading at 12:45 (-15 min): 110 mg/dL
    pre_reading = MockObservation(110.0, meal_time - timedelta(minutes=15), obs_id="pre-1")
    # Post-meal readings:
    # +45 min: 160 mg/dL
    # +90 min: 185 mg/dL (peak)
    # +150 min: 140 mg/dL
    post_1 = MockObservation(160.0, meal_time + timedelta(minutes=45), obs_id="post-1")
    post_2 = MockObservation(185.0, meal_time + timedelta(minutes=90), obs_id="post-2")
    post_3 = MockObservation(140.0, meal_time + timedelta(minutes=150), obs_id="post-3")

    items = calculate_meal_glucose_temporal_associations([meal], [pre_reading, post_1, post_2, post_3])

    assert len(items) == 1
    assoc = items[0]
    assert assoc.meal_id == "meal-1"
    assert assoc.description == "Katori Rice and Dal"
    assert assoc.pre_meal_glucose == 110.0
    assert assoc.post_meal_peak == 185.0
    assert assoc.delta_mg_dl == 75.0  # 185 - 110
    assert assoc.time_to_peak_minutes == 90
    assert "post-1" in assoc.associated_glucose_ids
    assert "post-2" in assoc.associated_glucose_ids
    assert "post-3" in assoc.associated_glucose_ids
    assert "+75.0 mg/dL" in assoc.relationship_note


def test_meal_glucose_no_readings():
    meal_time = datetime(2026, 9, 24, 13, 0, 0, tzinfo=timezone.utc)
    meal = MockMeal("meal-2", "Salad", meal_time)
    items = calculate_meal_glucose_temporal_associations([meal], [])
    assert len(items) == 0


# ==============================================================================
# 5. Longitudinal Comparison Tests
# ==============================================================================


def test_longitudinal_comparison():
    now = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)
    # Current 14 days (last 14 days): stable control (TIR ~ 80%, mean ~ 115)
    current_readings = [
        MockObservation(115.0, now - timedelta(days=i))
        for i in range(1, 10)
    ]
    # Previous 14 days (days 15-28): higher glucose (TIR ~ 30%, mean ~ 190)
    prev_readings = [
        MockObservation(190.0, now - timedelta(days=14 + i))
        for i in range(1, 10)
    ]

    comparison = calculate_longitudinal_comparison(
        current_readings + prev_readings,
        window_days=14,
        reference_date=now,
    )

    assert comparison.period_days == 14
    assert comparison.has_sufficient_history is True
    assert comparison.current_readings_count == 9
    assert comparison.previous_readings_count == 9

    # TIR comparison: 100% current vs 0% prev -> improving
    assert comparison.tir_comparison.trend_direction == "improving"
    assert comparison.tir_comparison.delta == 100.0

    # Mean comparison: 115.0 current vs 190.0 prev -> improving (lower is better)
    assert comparison.mean_comparison.trend_direction == "improving"
    assert comparison.mean_comparison.delta == -75.0


def test_longitudinal_comparison_insufficient_history():
    now = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)
    current_readings = [MockObservation(115.0, now - timedelta(days=1))]
    comparison = calculate_longitudinal_comparison(current_readings, window_days=14, reference_date=now)

    assert comparison.has_sufficient_history is False
    assert comparison.previous_readings_count == 0
    assert comparison.tir_comparison.trend_direction == "insufficient_data"


# ==============================================================================
# 6. Validated eGFR Equation Tests (2021 CKD-EPI)
# ==============================================================================


def test_egfr_ckd_epi_2021_female():
    # Female, Age 55, Creatinine 0.7 mg/dL (exact kappa)
    egfr = calculate_egfr_ckd_epi_2021(serum_creatinine_mg_dl=0.7, age_years=55, is_female=True)
    # Expected: 142 * (1.0)^(-0.241) * (1.0)^(-1.2) * (0.9938^55) * 1.012 = 142 * 0.7107 * 1.012 ~= 102.1
    assert 95.0 <= egfr <= 110.0

    # High creatinine (kidney impairment): e.g. 2.2 mg/dL
    egfr_impaired = calculate_egfr_ckd_epi_2021(serum_creatinine_mg_dl=2.2, age_years=60, is_female=True)
    assert egfr_impaired < 35.0


def test_egfr_ckd_epi_2021_male():
    # Male, Age 50, Creatinine 0.9 mg/dL (exact kappa)
    egfr = calculate_egfr_ckd_epi_2021(serum_creatinine_mg_dl=0.9, age_years=50, is_female=False)
    # Expected: 142 * (0.9938^50) ~= 142 * 0.733 ~= 104.1
    assert 98.0 <= egfr <= 110.0


def test_egfr_zero_or_negative():
    assert calculate_egfr_ckd_epi_2021(0.0) == 0.0
    assert calculate_egfr_ckd_epi_2021(-1.5) == 0.0


# ==============================================================================
# 7. Screening Status Engine Tests
# ==============================================================================


def test_screening_status_no_record():
    ref_dt = datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)
    status = calculate_screening_status("Eye Screening", "RETINOPATHY", None, interval_months=12, reference_dt=ref_dt)
    assert status.status == "OVERDUE"
    assert status.is_overdue is True
    assert status.last_completed_at is None
    assert status.due_date == "2026-09-24"


def test_screening_status_current():
    ref_dt = datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)
    completed_dt = ref_dt - timedelta(days=60)  # 2 months ago (interval 12 months)
    status = calculate_screening_status("Foot Screening", "NEUROPATHY", completed_dt, interval_months=12, reference_dt=ref_dt)
    assert status.status == "CURRENT"
    assert status.is_overdue is False


def test_screening_status_due_soon():
    ref_dt = datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)
    # 11 months and 20 days ago (due within ~10 days)
    completed_dt = ref_dt - timedelta(days=355)
    status = calculate_screening_status("Kidney Screening", "NEPHROPATHY", completed_dt, interval_months=12, reference_dt=ref_dt)
    assert status.status == "DUE_SOON"
    assert status.is_overdue is False


def test_screening_status_overdue():
    ref_dt = datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)
    completed_dt = ref_dt - timedelta(days=450)  # 15 months ago
    status = calculate_screening_status("Eye Screening", "RETINOPATHY", completed_dt, interval_months=12, reference_dt=ref_dt)
    assert status.status == "OVERDUE"
    assert status.is_overdue is True
