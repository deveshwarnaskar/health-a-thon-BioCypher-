"""PatientProfile entity placeholder (Gate 02B).

Deliberately minimal. Clinical telemetry context from the Aahaar prototype is
not duplicated here; it will be re-modelled in a later gate.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PatientProfile:
    id: UUID
    facility_id: UUID
    uh_id: str
    name: str
    created_at: datetime = field(default_factory=datetime.utcnow)