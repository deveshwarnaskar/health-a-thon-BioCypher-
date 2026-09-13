"""LogMealDraft command placeholder (Gate 02B).

A meal submitted by the patient/caregiver that has NOT yet been confirmed.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class LogMealDraft:
    command_id: UUID = field(default_factory=uuid4)
    patient_id: UUID | None = None
    description: str = ""