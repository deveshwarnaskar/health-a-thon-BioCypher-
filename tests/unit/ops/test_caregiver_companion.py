"""Unit tests for Proactive Caregiver Companion Service ("Health Saathi").

Verifies:
1. Morning fasting nudge generated when no fasting sugar logged.
2. Morning fasting nudge suppressed when fasting sugar is already logged.
3. Lunch nudge suppressed when lunch meal is already logged.
4. Hypoglycemia context continuity (gentle follow-up when previous reading was < 70 mg/dL).
5. Information Asymmetry: strictly no 'carb' or 'glycemic' terms in patient messages.
6. Quiet hours suppression (no proactive outreach between 22:00 and 07:00).
7. Daily frequency capping (max 3 proactive check-ins per day).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from backend.application.services.caregiver_companion import (
    CaregiverMilestone,
    evaluate_patient_caregiver_nudge,
    get_current_milestone,
    IST,
)


def _make_fake_patient(name="Subham Das", phone="+916291773811", active=True):
    p = MagicMock()
    p.id = uuid4()
    p.tenant_id = uuid4()
    p.name = name
    p.active = active
    p.phone = MagicMock()
    p.phone.value = phone
    return p


def _make_fake_uow(glucose_list=None, meals_list=None, notifs_list=None):
    uow = MagicMock()
    uow.glucose_observations.list_for_patient.return_value = glucose_list or []
    uow.meal_observations.list_for_patient.return_value = meals_list or []
    uow.notifications.list_for_patient.return_value = notifs_list or []
    return uow


def test_morning_fasting_nudge_generated():
    patient = _make_fake_patient()
    uow = _make_fake_uow()
    # 08:00 AM IST
    morning_utc = datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc)  # 08:00 AM IST

    nudge = evaluate_patient_caregiver_nudge(patient, uow, now_utc=morning_utc)
    assert nudge is not None
    assert nudge.milestone == CaregiverMilestone.MORNING_FASTING
    assert "Namaste Subham ji" in nudge.message_text or "Good morning Subham ji" in nudge.message_text
    assert "fasting sugar" in nudge.message_text.lower()
    assert nudge.recipient_phone == "+916291773811"


def test_morning_fasting_nudge_suppressed_when_already_logged():
    patient = _make_fake_patient()
    # Patient already logged fasting sugar at 07:45 AM IST
    g = MagicMock()
    g.taken_at = datetime(2026, 9, 21, 2, 15, tzinfo=timezone.utc)
    g.tag = "FASTING"
    g.value = MagicMock()
    g.value.mg_dl = 112

    uow = _make_fake_uow(glucose_list=[g])
    morning_utc = datetime(2026, 9, 21, 2, 45, tzinfo=timezone.utc)  # 08:15 AM IST

    nudge = evaluate_patient_caregiver_nudge(patient, uow, now_utc=morning_utc)
    assert nudge is None, "Morning fasting nudge must be suppressed if patient already logged fasting sugar today"


def test_lunch_nudge_suppressed_when_already_logged():
    patient = _make_fake_patient()
    # Patient already logged lunch at 01:15 PM IST
    m = MagicMock()
    m.recorded_at = datetime(2026, 9, 21, 7, 45, tzinfo=timezone.utc)  # 01:15 PM IST
    m.description = "2 roti and dal"

    uow = _make_fake_uow(meals_list=[m])
    lunch_time_utc = datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc)  # 01:30 PM IST

    nudge = evaluate_patient_caregiver_nudge(patient, uow, now_utc=lunch_time_utc)
    assert nudge is None, "Lunch nudge must be suppressed if lunch is already logged"


def test_hypoglycemia_context_followup():
    patient = _make_fake_patient()
    # Patient had low sugar (62 mg/dL) yesterday evening (9:30 PM IST = 16:00 UTC)
    g = MagicMock()
    g.taken_at = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)
    g.tag = "POST_DINNER"
    g.value = MagicMock()
    g.value.mg_dl = 62

    uow = _make_fake_uow(glucose_list=[g])
    morning_utc = datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc)  # 08:00 AM IST

    nudge = evaluate_patient_caregiver_nudge(patient, uow, now_utc=morning_utc)
    assert nudge is not None
    assert nudge.urgency == "follow_up"
    assert "low (hypo)" in nudge.message_text.lower()


def test_quiet_hours_suppression():
    patient = _make_fake_patient()
    uow = _make_fake_uow()
    # 02:00 AM IST = 20:30 UTC previous day
    night_utc = datetime(2026, 9, 20, 20, 30, tzinfo=timezone.utc)

    nudge = evaluate_patient_caregiver_nudge(patient, uow, now_utc=night_utc)
    assert nudge is None, "Proactive nudges must never be sent during quiet hours (22:00 - 07:00)"


def test_daily_frequency_capping():
    patient = _make_fake_patient()
    # 3 nudges were already sent today
    n1 = MagicMock(created_at=datetime(2026, 9, 21, 3, 0, tzinfo=timezone.utc))
    n2 = MagicMock(created_at=datetime(2026, 9, 21, 6, 0, tzinfo=timezone.utc))
    n3 = MagicMock(created_at=datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc))

    uow = _make_fake_uow(notifs_list=[n1, n2, n3])
    afternoon_utc = datetime(2026, 9, 21, 12, 30, tzinfo=timezone.utc)  # 06:00 PM IST

    nudge = evaluate_patient_caregiver_nudge(patient, uow, now_utc=afternoon_utc)
    assert nudge is None, "Daily frequency cap (max 3) must suppress additional automated nudges"


def test_information_asymmetry_all_milestones():
    patient = _make_fake_patient()
    uow = _make_fake_uow()

    for milestone in CaregiverMilestone:
        nudge = evaluate_patient_caregiver_nudge(
            patient,
            uow,
            now_utc=datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc),
            force_milestone=milestone,
        )
        assert nudge is not None
        lower_msg = nudge.message_text.lower()
        # Invariant: Patient-facing chat must NEVER expose raw carbs or glycemic index
        assert "carb" not in lower_msg, f"Found 'carb' in milestone {milestone}"
        assert "glycemic" not in lower_msg, f"Found 'glycemic' in milestone {milestone}"
