"""UHID value object (Gate 03)."""

import re
from dataclasses import dataclass

from ..exceptions import DomainValidationError

_UHID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{2,31}$")


@dataclass(frozen=True)
class UHID:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _UHID_PATTERN.match(self.value):
            raise DomainValidationError(f"invalid UHID {self.value!r}")

    def __str__(self) -> str:
        return self.value