"""ReassignCareTask use case (Gate 10J-B)."""

from ..commands import ReassignCareTask
from ..dtos.results import CareTaskReassignedResult
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.events import CareTaskReassigned
from ._transaction import in_transaction


class ReassignCareTaskHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        events: DomainEventPublisher,
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow = uow
        self._events = events
        self._clock = clock
        self._id_gen = id_gen

    def handle(self, cmd: ReassignCareTask) -> CareTaskReassignedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: ReassignCareTask) -> CareTaskReassignedResult:
        task = self._uow.care_tasks.get(cmd.care_task_id)
        task.reassign(cmd.new_user_id)
        self._uow.care_tasks.save(task)
        self._events.publish(
            CareTaskReassigned(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=task.patient_id,
                correlation_id=cmd.correlation_id,
                care_task_id=task.id,
            )
        )
        return CareTaskReassignedResult(
            care_task_id=task.id,
            assigned_to_user_id=task.assigned_to_user_id,
            status=task.status.value,
        )
