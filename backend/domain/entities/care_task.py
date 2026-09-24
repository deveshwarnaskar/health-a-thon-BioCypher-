"""CareTask entity (Gate 03).

Care-team task with an explicit lifecycle state machine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from ..exceptions import InvalidStateTransition


class CareTaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


_TRANSITIONS = {
    CareTaskStatus.OPEN: {CareTaskStatus.IN_PROGRESS, CareTaskStatus.COMPLETED, CareTaskStatus.CANCELLED},
    CareTaskStatus.IN_PROGRESS: {CareTaskStatus.COMPLETED, CareTaskStatus.CANCELLED},
    CareTaskStatus.COMPLETED: set(),
    CareTaskStatus.CANCELLED: set(),
}


@dataclass
class CareTask:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    assigned_to_user_id: UUID = field(default_factory=uuid4)
    description: str = ""
    status: CareTaskStatus = CareTaskStatus.OPEN
    due_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    def _transition(self, target: CareTaskStatus) -> None:
        allowed = _TRANSITIONS.get(self.status)
        if allowed is None or target not in allowed:
            raise InvalidStateTransition(
                f"care task cannot move {self.status.value} -> {target.value}"
            )
        self.status = target

    def start(self) -> None:
        self._transition(CareTaskStatus.IN_PROGRESS)

    def complete(self) -> None:
        self._transition(CareTaskStatus.COMPLETED)
        self.completed_at = datetime.utcnow()

    def cancel(self) -> None:
        self._transition(CareTaskStatus.CANCELLED)

    def reassign(self, new_user_id: UUID) -> None:
        if self.status in {CareTaskStatus.COMPLETED, CareTaskStatus.CANCELLED}:
            raise InvalidStateTransition(
                f"cannot reassign a {self.status.value} task"
            )
        self.assigned_to_user_id = new_user_id