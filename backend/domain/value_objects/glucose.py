"""Glucose domain value objects (Gate 03).

``GlucoseValue`` enforces the established safe parse boundary. This is data
validation only — explicitly NOT a clinical diagnosis or risk engine.
"""

from dataclasses import dataclass, field
from datetime import datetime

from ..exceptions import InvalidGlucoseValue
from .reading_tag import ReadingTag

MIN_GLUCOSE_MGDL = 20
MAX_GLUCOSE_MGDL = 600


@dataclass(frozen=True)
class GlucoseValue:
    value_mg_dl: int

    def __post_init__(self) -> None:
        if isinstance(self.value_mg_dl, bool) or not isinstance(self.value_mg_dl, int):
            raise InvalidGlucoseValue(
                f"glucose must be an integer, got {self.value_mg_dl!r}"
            )
        if not MIN_GLUCOSE_MGDL <= self.value_mg_dl <= MAX_GLUCOSE_MGDL:
            raise InvalidGlucoseValue(
                f"glucose {self.value_mg_dl} outside safe boundary "
                f"{MIN_GLUCOSE_MGDL}-{MAX_GLUCOSE_MGDL} mg/dL"
            )

    def __str__(self) -> str:
        return f"{self.value_mg_dl} mg/dL"


@dataclass(frozen=True)
class GlucoseMeasurement:
    """A single glucose reading: validated value + context (kept for the
    existing observation use case and legacy-normalized intake)."""

    value: GlucoseValue
    taken_at: datetime = field(default_factory=datetime.utcnow)
    tag: ReadingTag | None = None