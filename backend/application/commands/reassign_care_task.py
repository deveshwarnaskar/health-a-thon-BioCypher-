"""ReassignCareTask command (Gate 10J-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ReassignCareTask:
    care_task_id: UUID
    new_user_id: UUID
    correlation_id: UUID | None = None
