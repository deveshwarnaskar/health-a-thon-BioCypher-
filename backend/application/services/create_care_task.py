"""CreateCareTask use case (Gate 04)."""

from ..commands import CreateCareTask
from ..dtos.results import CareTaskCreatedResult
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import CareTask
from ...domain.events import CareTaskCreated
from ._transaction import in_transaction


class CreateCareTaskHandler:
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

    def handle(self, cmd: CreateCareTask) -> CareTaskCreatedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: CreateCareTask) -> CareTaskCreatedResult:
        self._uow.patients.get(cmd.patient_id)
        task = CareTask(
            id=self._id_gen.new_uuid(),
            patient_id=cmd.patient_id,
            assigned_to_user_id=cmd.assigned_to_user_id,
            description=cmd.description,
            due_at=cmd.due_at,
            created_at=self._clock.now(),
        )
        self._uow.care_tasks.add(task)
        self._events.publish(
            CareTaskCreated(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=cmd.patient_id,
                correlation_id=cmd.correlation_id,
                care_task_id=task.id,
            )
        )
        return CareTaskCreatedResult(
            care_task_id=task.id,
            patient_id=cmd.patient_id,
            status=task.status.value,
            due_at=task.due_at,
        )