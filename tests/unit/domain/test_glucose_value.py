"""Gate 03 — GlucoseValue invariants."""

import pytest

from backend.domain.exceptions import InvalidGlucoseValue
from backend.domain.value_objects import GlucoseValue


def test_accepts_minimum_20():
    g = GlucoseValue(20)
    assert g.value_mg_dl == 20


def test_accepts_maximum_600():
    g = GlucoseValue(600)
    assert g.value_mg_dl == 600


def test_rejects_below_20():
    with pytest.raises(InvalidGlucoseValue):
        GlucoseValue(19)


def test_rejects_above_600():
    with pytest.raises(InvalidGlucoseValue):
        GlucoseValue(601)


def test_rejects_non_integer():
    with pytest.raises(InvalidGlucoseValue):
        GlucoseValue(120.5)


def test_string_representation():
    assert str(GlucoseValue(140)) == "140 mg/dL"