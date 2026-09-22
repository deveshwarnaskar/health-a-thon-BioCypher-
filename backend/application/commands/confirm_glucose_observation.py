"""ConfirmGlucoseObservation command (Gate 04).

Patient-side confirmation (or correction) of a pending glucose observation via
the WhatsApp channel. The domain entity applies its own ``confirm`` /
``reject`` transitions; this command never invents values — the corrected value
is a validated ``GlucoseValue`` supplied by the caller.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional
from uuid import UUID

from ...domain.value_objects import GlucoseValue, PhoneNumber, ReadingTag


@dataclass(frozen=True)
class ConfirmGlucoseObservation:
    observation_id: UUID
    confirmed_by: PhoneNumber
    corrected_value: Optional[GlucoseValue] = None
    corrected_tag: Optional[ReadingTag] = None
    corrected_taken_at: Optional[datetime] = None
    correlation_id: Optional[UUID] = None
    source_metadata: Optional[Mapping[str, object]] = None