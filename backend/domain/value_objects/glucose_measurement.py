"""GlucoseMeasurement value object placeholder (Gate 02B)."""

from dataclasses import dataclass
from datetime import datetime

from ..value_objects.reading_tag import ReadingTag


@dataclass(frozen=True)
class GlucoseMeasurement:
    value_mg_dl: int
    taken_at: datetime
    tag: ReadingTag | None = None