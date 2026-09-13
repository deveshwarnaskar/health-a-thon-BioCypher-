"""PhoneNumber value object placeholder (Gate 02B).

E.164 country-code-first normalization is enforced by the legacy parser today;
this boundary reserves the canonical type.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PhoneNumber:
    value: str