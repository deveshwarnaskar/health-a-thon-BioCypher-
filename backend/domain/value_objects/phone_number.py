"""PhoneNumber value object (Gate 03).

Normalization and structural validation only. Independent of any WhatsApp/Meta
SDK, and provides a masked representation so logs never store or display the
full number unnecessarily.
"""

import re
from dataclasses import dataclass

from ..exceptions import InvalidPhoneNumber

_DIGITS = re.compile(r"^[0-9]+$")
_MIN_E164_DIGITS = 7
_MAX_E164_DIGITS = 15


def normalize_raw(raw: str) -> str:
    """Normalize a raw phone string to '+' + digits (E.164-style shape).

    Accepts spaces, dashes, dots, parens; drops all but an optional leading '+'.
    """
    if raw is None:
        raise InvalidPhoneNumber("phone number is required")
    compact = re.sub(r"[^0-9+]", "", str(raw).strip())
    if not compact:
        raise InvalidPhoneNumber(f"phone number {raw!r} contains no digits")
    if compact.count("+") > 1:
        raise InvalidPhoneNumber(f"phone number {raw!r} is malformed")
    return compact


@dataclass(frozen=True)
class PhoneNumber:
    value: str

    def __post_init__(self) -> None:
        normalized = normalize_raw(self.value)
        digits = normalized.lstrip("+")
        if not _DIGITS.match(digits):
            raise InvalidPhoneNumber(f"phone number {self.value!r} is malformed")
        if not _MIN_E164_DIGITS <= len(digits) <= _MAX_E164_DIGITS:
            raise InvalidPhoneNumber(
                f"phone number {self.value!r} must contain between "
                f"{_MIN_E164_DIGITS} and {_MAX_E164_DIGITS} digits"
            )
        object.__setattr__(self, "value", normalized)

    @property
    def digits(self) -> str:
        return self.value.lstrip("+")

    @property
    def masked(self) -> str:
        """Log-safe representation: keeps '+' and the last four digits.

        Example: '+917439030190' -> '+********0190'.
        """
        digits = self.digits
        keep = digits[-4:]
        masked_digits = "*" * (len(digits) - 4) + keep
        return f"+{masked_digits}"

    def __str__(self) -> str:
        return self.value