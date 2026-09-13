"""IngestGlucoseReading command placeholder (Gate 02B)."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from ...domain.value_objects.glucose_measurement import GlucoseMeasurement


@dataclass(frozen=True)
class IngestGlucoseReading:
    command_id: UUID = field(default_factory=uuid4)
    patient_profile_id: UUID | None = None
    measurement: GlucoseMeasurement | None = None