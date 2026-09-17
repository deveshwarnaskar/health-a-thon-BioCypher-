"""AdminDeactivatePatient use case (Gate 10K-B)."""

from backend.application.commands.admin_deactivate_patient import AdminDeactivatePatient
from backend.application.dtos.admin import AdminPatientSummaryResult
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services._transaction import in_transaction
from backend.domain.events.admin import PatientDeactivated


class AdminDeactivatePatientHandler:
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

    def handle(self, cmd: AdminDeactivatePatient) -> AdminPatientSummaryResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: AdminDeactivatePatient) -> AdminPatientSummaryResult:
        patient = self._uow.patients.get(cmd.patient_id)
        patient.active = False
        self._uow.patients.save(patient)
        self._events.publish(
            PatientDeactivated(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                correlation_id=cmd.correlation_id,
                patient_id=patient.id,
            )
        )
        mapping = self._uow.identity_mappings.get_by_patient_id(patient.id)
        has_active = bool(mapping and mapping.active)
        return AdminPatientSummaryResult(
            patient_id=patient.id,
            uh_id=patient.uh_id.value,
            name=patient.name,
            facility_id=patient.facility_id,
            phone=patient.phone.value if patient.phone else None,
            active=patient.active,
            has_active_mapping=has_active,
            created_at=patient.created_at,
        )
