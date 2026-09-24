"""LinkPatientPhone use case (Gate 04)."""

from ..commands import LinkPatientPhone
from ..dtos.results import PhoneLinked
from ..ports.unit_of_work import UnitOfWork
from ._transaction import in_transaction


class LinkPatientPhoneHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, cmd: LinkPatientPhone) -> PhoneLinked:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: LinkPatientPhone) -> PhoneLinked:
        patient = self._uow.patients.get(cmd.patient_id)
        patient.link_phone(cmd.phone)
        self._uow.patients.save(patient)
        return PhoneLinked(patient_id=cmd.patient_id, phone_masked=cmd.phone.masked)