"""CompleteCareTask command (Gate 04)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CompleteCareTask:
    care_task_id: UUID
    correlation_id: UUID | None = None