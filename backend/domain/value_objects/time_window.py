"""TimeWindow value object (Gate 03)."""

from dataclasses import dataclass
from datetime import date

from ..exceptions import DomainValidationError


@dataclass(frozen=True)
class TimeWindow:
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise DomainValidationError(
                f"window start {self.start_date} is after end {self.end_date}"
            )