"""TimeWindow value object placeholder (Gate 02B)."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TimeWindow:
    start_date: date
    end_date: date