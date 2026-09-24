"""CreateCareTask command (Gate 04)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CreateCareTask:
    patient_id: UUID
    assigned_to_user_id: UUID
    description: str
    due_at: datetime | None = None
    correlation_id: UUID | None = None