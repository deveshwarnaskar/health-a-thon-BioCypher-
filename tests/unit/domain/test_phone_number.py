"""Gate 03 — PhoneNumber normalization, validation, and masking."""

import pytest

from backend.domain.exceptions import InvalidPhoneNumber
from backend.domain.value_objects import PhoneNumber


def test_normalizes_spaces_and_dashes():
    assert PhoneNumber("+91 74390 30190").value == "+917439030190"
    assert PhoneNumber("+91-74390-30190").value == "+917439030190"


def test_normalizes_dots_and_parens():
    assert PhoneNumber("(91) 743.903.0190").value == "917439030190"


def test_rejects_empty():
    with pytest.raises(InvalidPhoneNumber):
        PhoneNumber("")


def test_rejects_non_numeric():
    with pytest.raises(InvalidPhoneNumber):
        PhoneNumber("+91 CALL ME")


def test_rejects_too_short():
    with pytest.raises(InvalidPhoneNumber):
        PhoneNumber("+91 123")


def test_rejects_too_long():
    with pytest.raises(InvalidPhoneNumber):
        PhoneNumber("+1" + "9" * 20)


def test_mask_never_exposes_full_number():
    p = PhoneNumber("+917439030190")
    masked = p.masked
    assert masked != p.value
    assert masked.endswith("0190")
    assert "7439030190" not in masked
    assert p.value == "+917439030190"


def test_digits():
    p = PhoneNumber("+917439030190")
    assert p.digits == "917439030190"