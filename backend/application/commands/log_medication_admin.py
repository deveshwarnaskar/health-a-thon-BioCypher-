"""LogMedicationAdmin command placeholder (Gate 02B).

Records a medication administration event. The prescription itself originates
exclusively from licensed clinicians (Gate 01.1).
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class LogMedicationAdmin:
    command_id: UUID = field(default_factory=uuid4)
    medication_plan_id: UUID | None = None
    administered_at: datetime | None = None