"""CompleteCareTask use case (Gate 04)."""

from ..commands import CompleteCareTask
from ..dtos.results import CareTaskCompletedResult
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.events import CareTaskCompleted
from ._transaction import in_transaction


class CompleteCareTaskHandler:
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

    def handle(self, cmd: CompleteCareTask) -> CareTaskCompletedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: CompleteCareTask) -> CareTaskCompletedResult:
        task = self._uow.care_tasks.get(cmd.care_task_id)
        task.complete()
        self._uow.care_tasks.save(task)
        self._events.publish(
            CareTaskCompleted(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=task.patient_id,
                correlation_id=cmd.correlation_id,
                care_task_id=task.id,
            )
        )
        return CareTaskCompletedResult(
            care_task_id=task.id,
            status=task.status.value,
            completed_at=task.completed_at,
        )