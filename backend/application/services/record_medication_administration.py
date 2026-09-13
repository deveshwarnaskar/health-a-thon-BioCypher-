"""RecordMedicationAdministration use case (Gate 04).

PATIENT-side adherence event against a clinician-authored MedicationPlan.

This is NOT prescription: the plan is loaded read-only, must exist and be
active, and is never created, titrated, or modified here. The administration
fact is emitted as the canonical ``MedicationAdministrationRecorded`` domain
event. (Gate 03 defines no medication-administration entity, so the event is
the record surface; persistence of a first-class record is a documented later
gate limitation.)
"""

from ..commands import RecordMedicationAdministration
from ..dtos.results import AdministrationRecorded
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.events import MedicationAdministrationRecorded
from ...domain.exceptions import DomainValidationError
from ._transaction import in_transaction


class RecordMedicationAdministrationHandler:
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

    def handle(self, cmd: RecordMedicationAdministration) -> AdministrationRecorded:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: RecordMedicationAdministration) -> AdministrationRecorded:
        plan = self._uow.medication_plans.get(cmd.medication_plan_id)
        if not plan.active:
            raise DomainValidationError("medication plan is not active")
        self._events.publish(
            MedicationAdministrationRecorded(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=plan.patient_id,
                correlation_id=cmd.correlation_id,
                medication_plan_id=plan.id,
            )
        )
        return AdministrationRecorded(
            medication_plan_id=plan.id,
            patient_id=plan.patient_id,
            administered_at=cmd.administered_at,
        )