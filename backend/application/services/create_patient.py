"""CreatePatient use case (Gate 10H-B).

Administrator provisioning of a tenant patient record. Tenant/facility scoping
is applied by the authenticated admin's tenant context + RLS; the handler never
accepts a tenant from the command.
"""

from ..commands import CreatePatient
from ..dtos.results import PatientProvisionedResult
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import Patient
from ...domain.events import PatientProvisioned
from ...domain.value_objects import UHID
from ._transaction import in_transaction


class CreatePatientHandler:
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

    def handle(self, cmd: CreatePatient) -> PatientProvisionedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: CreatePatient) -> PatientProvisionedResult:
        patient = Patient(
            id=self._id_gen.new_uuid(),
            uh_id=cmd.uh_id or UHID("UNASSIGNED"),
            name=cmd.name,
            phone=cmd.phone,
            facility_id=cmd.facility_id,
            active=True,
            created_at=self._clock.now(),
        )
        self._uow.patients.add(patient)
        self._events.publish(
            PatientProvisioned(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=patient.id,
                correlation_id=cmd.correlation_id,
            )
        )
        return PatientProvisionedResult(
            patient_id=patient.id,
            uh_id=patient.uh_id.value,
            name=patient.name,
            facility_id=patient.facility_id,
            active=patient.active,
            created_at=patient.created_at,
        )