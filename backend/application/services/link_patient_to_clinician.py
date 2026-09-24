"""LinkPatientToClinician use case (Gate 13).

Patient-initiated, bidirectional patient↔clinician connection created when a
patient scans a clinician's account QR code. The handler:

1. resolves & validates the clinician (care_team_members, active,
   must belong to a facility),
2. enrolls the patient into the clinician's facility (so the clinician's
   facility-scoped reads and monitoring cohort can resolve the patient),
3. creates an idempotent ACTIVE PatientClinicianLink (one active link per
   (tenant, patient, clinician) pair),
4. emits ``patient_clinician_link.created`` through the transactional outbox.

There is no separate consent step — scanning IS the patient's consent. A link
is idempotent: linking the same clinician twice re-uses the existing link.
"""

from ..commands import LinkPatientToClinician
from ..dtos.results import PatientClinicianLinkedResult
from ..exceptions import ClinicianUnavailable
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import PatientClinicianLink
from ...domain.events import PatientClinicianLinked
from ._transaction import in_transaction


class LinkPatientToClinicianHandler:
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

    def handle(self, cmd: LinkPatientToClinician) -> PatientClinicianLinkedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: LinkPatientToClinician) -> PatientClinicianLinkedResult:
        member = self._uow.care_team_members.get(cmd.clinician_user_id)
        if not member.active or member.facility_id is None:
            raise ClinicianUnavailable(
                "the account is not an active clinician assigned to a facility"
            )

        patient = self._uow.patients.get(cmd.patient_id)

        existing = self._uow.patient_clinician_links.find_by_active_pair(
            cmd.patient_id, cmd.clinician_user_id
        )
        if existing is not None:
            return self._to_result(existing)

        now = self._clock.now()
        link = PatientClinicianLink(
            id=self._id_gen.new_uuid(),
            patient_id=cmd.patient_id,
            clinician_user_id=cmd.clinician_user_id,
            facility_id=member.facility_id,
            clinician_name=member.display_name,
            active=True,
            created_at=now,
            updated_at=now,
        )
        self._uow.patient_clinician_links.add(link)

        if patient.facility_id != member.facility_id:
            patient.enroll_facility(member.facility_id)
            self._uow.patients.save(patient)

        self._events.publish(
            PatientClinicianLinked(
                event_id=self._id_gen.new_uuid(),
                occurred_at=now,
                patient_id=cmd.patient_id,
                correlation_id=cmd.correlation_id,
                link_id=link.id,
                clinician_user_id=cmd.clinician_user_id,
            )
        )
        return self._to_result(link)

    def _to_result(self, link: PatientClinicianLink) -> PatientClinicianLinkedResult:
        return PatientClinicianLinkedResult(
            link_id=link.id,
            patient_id=link.patient_id,
            clinician_user_id=link.clinician_user_id,
            clinician_name=link.clinician_name,
            facility_id=link.facility_id,
            created_at=link.created_at,
        )