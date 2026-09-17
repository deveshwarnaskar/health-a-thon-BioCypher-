"""StartCareTask command (Gate 10J-B)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StartCareTask:
    care_task_id: UUID
    correlation_id: UUID | None = None
