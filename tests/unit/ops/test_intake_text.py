"""Gate 09 — unit tests: WhatsApp free-text intake transform."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.application.commands import IngestGlucoseReading, LogMealDraft
from backend.application.ops.intake_text import dispatch_hint, parse_intake_text
from backend.domain.exceptions import DomainError
from backend.domain.value_objects import ReadingTag


def _parse(text: str):
    return parse_intake_text(
        text,
        patient_id=uuid4(),
        correlation_id=uuid4(),
        recorded_at=datetime.now(timezone.utc),
    )


class TestGlucoseDetection:
    def test_bare_number_is_glucose(self):
        cmd = _parse("180")
        assert isinstance(cmd, IngestGlucoseReading)
        assert cmd.value.value_mg_dl == 180
        assert dispatch_hint(cmd) == "GLUCOSE"

    def test_fasting_alias(self):
        cmd = _parse("180 fasting")
        assert isinstance(cmd, IngestGlucoseReading)
        assert cmd.tag is ReadingTag.FASTING

    def test_post_dinner_multi_word_alias(self):
        cmd = _parse("190  after dinner")
        assert isinstance(cmd, IngestGlucoseReading)
        assert cmd.tag is ReadingTag.POST_DINNER

    def test_post_lunch_alias(self):
        cmd = _parse("170 post lunch")
        assert isinstance(cmd, IngestGlucoseReading)
        assert cmd.tag is ReadingTag.POST_LUNCH

    def test_pre_meal_alias(self):
        cmd = _parse("95 before meal")
        assert isinstance(cmd, IngestGlucoseReading)
        assert cmd.tag is ReadingTag.PRE_MEAL

    def test_leading_trailing_whitespace_tolerated(self):
        cmd = _parse("  200 fasting  ")
        assert isinstance(cmd, IngestGlucoseReading)
        assert cmd.value.value_mg_dl == 200

    def test_out_of_range_value_raises_domain_error(self):
        with pytest.raises(DomainError):
            _parse("999")

    def test_below_domain_floor_raises_domain_error(self):
        with pytest.raises(DomainError):
            _parse("12")

    def test_two_digit_in_range_is_glucose(self):
        cmd = _parse("50")
        assert isinstance(cmd, IngestGlucoseReading)
        assert cmd.value.value_mg_dl == 50


class TestMealDraftFallback:
    def test_free_text_is_meal_draft(self):
        cmd = _parse("dal rice and salad")
        assert isinstance(cmd, LogMealDraft)
        assert cmd.description == "dal rice and salad"
        assert dispatch_hint(cmd) == "MEAL"

    def test_unknown_tag_is_meal_draft(self):
        cmd = _parse("180 weirdthing")
        assert isinstance(cmd, LogMealDraft)

    def test_empty_text_is_meal_draft(self):
        cmd = _parse("   ")
        assert isinstance(cmd, LogMealDraft)
        assert cmd.description == ""