"""Gate 03 — KatoriVolume invariants."""

import pytest

from backend.domain.exceptions import InvalidKatoriVolume
from backend.domain.value_objects import KatoriVolume


def test_accepts_small_150():
    assert KatoriVolume(150).volume_ml == 150


def test_accepts_medium_220():
    assert KatoriVolume(220).volume_ml == 220


def test_accepts_large_350():
    assert KatoriVolume(350).volume_ml == 350


def test_unsupported_volume_rejected():
    with pytest.raises(InvalidKatoriVolume):
        KatoriVolume(250)


def test_canonical_labels():
    assert KatoriVolume(150).label == "small"
    assert KatoriVolume(220).label == "medium"
    assert KatoriVolume(350).label == "large"


def test_non_integer_rejected():
    with pytest.raises(InvalidKatoriVolume):
        KatoriVolume(220.0)