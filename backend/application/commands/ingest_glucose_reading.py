"""IngestGlucoseReading command (Gate 04).

Patient-originated glucose reading. Validated value travels as a domain value
object; required input is enforced by the command shape (no Optional on
required fields).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from uuid import UUID

from ...domain.value_objects import GlucoseValue, ReadingTag


@dataclass(frozen=True)
class IngestGlucoseReading:
    patient_id: UUID
    value: GlucoseValue
    taken_at: datetime
    tag: ReadingTag | None = None
    correlation_id: UUID | None = None
    # Provenance of how the reading was produced (voice/text provider metadata)
    source_metadata: Mapping[str, object] | None = None