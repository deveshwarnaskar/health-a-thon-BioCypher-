"""IngestGlucoseReading command placeholder (Gate 02B)."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from ...domain.value_objects.glucose import GlucoseValue


@dataclass(frozen=True)
class IngestGlucoseReading:
    command_id: UUID = field(default_factory=uuid4)
    patient_id: UUID | None = None
    value: GlucoseValue | None = None