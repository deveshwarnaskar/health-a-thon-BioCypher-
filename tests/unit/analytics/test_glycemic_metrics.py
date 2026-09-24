"""Unit tests for glycemic metrics engine (TIR, CVI, Pearson r, meal slots, adherence)."""

from __future__ import annotations

import pytest

from backend.domain.services.glycemic_metrics import (
    GLUCOSE_HIGH,
    GLUCOSE_LOW,
    compute_window_metrics,
)


class TestGlycemicMetrics:
    def test_empty_inputs_return_clean_zero_metrics(self):
        res = compute_window_metrics(readings=[], meals=[], window_days=14)
        assert res["total_readings"] == 0
        assert res["total_confirmed_meals"] == 0
        assert res["active_logging_days"] == 0
        assert res["adherence_index"] == 0.0
        assert res["tir_in_range_pct"] == 0.0
        assert res["tir_above_range_pct"] == 0.0
        assert res["tir_below_range_pct"] == 0.0
        assert res["mean_glucose"] is None
        assert res["cvi"] is None
        assert res["pearson_r"] is None

    def test_tir_calculation(self):
        readings = [
            {"value": 65, "tag": "fasting", "taken_at": "2026-09-01T08:00:00Z"},   # Below (<70)
            {"value": 110, "tag": "fasting", "taken_at": "2026-09-02T08:00:00Z"},  # In (70-180)
            {"value": 140, "tag": "postlunch", "taken_at": "2026-09-02T13:00:00Z"}, # In (70-180)
            {"value": 220, "tag": "postdinner", "taken_at": "2026-09-02T20:00:00Z"}, # Above (>180)
        ]
        res = compute_window_metrics(readings=readings, meals=[], window_days=14)
        assert res["total_readings"] == 4
        assert res["tir_in_range_pct"] == 50.0   # 2 of 4
        assert res["tir_above_range_pct"] == 25.0  # 1 of 4
        assert res["tir_below_range_pct"] == 25.0  # 1 of 4
        assert res["mean_glucose"] == 133.8
        assert res["min_glucose"] == 65.0
        assert res["max_glucose"] == 220.0

    def test_adherence_index(self):
        readings = [
            {"value": 100, "taken_at": "2026-09-01T08:00:00Z"},
            {"value": 120, "taken_at": "2026-09-01T14:00:00Z"},
            {"value": 110, "taken_at": "2026-09-02T08:00:00Z"},
            {"value": 115, "taken_at": "2026-09-05T08:00:00Z"},
        ]
        # 3 unique days logged over a 10-day window -> 30%
        res = compute_window_metrics(readings=readings, meals=[], window_days=10)
        assert res["active_logging_days"] == 3
        assert res["adherence_index"] == 30.0

    def test_meal_slot_assignment_and_weekday_weekend(self):
        # 2026-09-01 is Tuesday (weekday), 2026-09-06 is Sunday (weekend)
        readings = [
            {"value": 150, "tag": "postbreakfast", "taken_at": "2026-09-01T09:00:00Z"},
            {"value": 160, "tag": "postbreakfast", "taken_at": "2026-09-06T09:30:00Z"},
            {"value": 180, "tag": "postlunch", "taken_at": "2026-09-01T14:00:00Z"},
            {"value": 200, "tag": "postdinner", "taken_at": "2026-09-01T21:00:00Z"},
        ]
        res = compute_window_metrics(readings=readings, meals=[], window_days=14)
        assert res["slot_pb"]["count"] == 2
        assert res["slot_pb"]["weekday"] == 150.0
        assert res["slot_pb"]["weekend"] == 160.0
        assert res["slot_pb"]["mean"] == 155.0
        assert res["slot_pl"]["count"] == 1
        assert res["slot_pl"]["mean"] == 180.0
        assert res["slot_pd"]["count"] == 1
        assert res["slot_pd"]["mean"] == 200.0

    def test_cvi_and_pearson_correlation(self):
        # 3 days with confirmed meals and postprandial glucose
        # Day 1: Low GI -> lower PPBG
        # Day 2: Med GI -> med PPBG
        # Day 3: High GI -> higher PPBG
        readings = [
            {"value": 120, "tag": "postlunch", "taken_at": "2026-09-01T13:00:00Z"},
            {"value": 150, "tag": "postlunch", "taken_at": "2026-09-02T13:00:00Z"},
            {"value": 210, "tag": "postlunch", "taken_at": "2026-09-03T13:00:00Z"},
        ]
        meals = [
            {"carbs_grams": 30.0, "gi_category": "low", "recorded_at": "2026-09-01T12:00:00Z", "confirmation": "confirmed"},
            {"carbs_grams": 45.0, "gi_category": "med", "recorded_at": "2026-09-02T12:00:00Z", "confirmation": "confirmed"},
            {"carbs_grams": 75.0, "gi_category": "high", "recorded_at": "2026-09-03T12:00:00Z", "confirmation": "confirmed"},
            # Pending meal should be ignored in confirmed calculations
            {"carbs_grams": 100.0, "gi_category": "high", "recorded_at": "2026-09-04T12:00:00Z", "confirmation": "pending"},
        ]
        res = compute_window_metrics(readings=readings, meals=meals, window_days=14)
        assert res["total_confirmed_meals"] == 3
        assert res["cvi"] is not None
        assert res["cvi"] > 0
        # Positive Pearson correlation between high GI share and PPBG
        assert res["pearson_r"] is not None
        assert res["pearson_r"] > 0.5
