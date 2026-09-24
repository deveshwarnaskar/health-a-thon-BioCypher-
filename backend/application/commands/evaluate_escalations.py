"""EvaluateEscalations command placeholder (Gate 02B).

Idempotent operational nudge engine (21:00 caregiver/patient follow-up),
mirroring the prototype's ``due_escalations`` behaviour as a future use case.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class EvaluateEscalations:
    command_id: UUID = field(default_factory=uuid4)
    facility_id: UUID | None = None
    now: datetime | None = None