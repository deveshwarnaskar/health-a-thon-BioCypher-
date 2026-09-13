"""GlucoseObservation entity (Gate 03).

Patient-originated glucose reading carrying a validated ``GlucoseValue`` and
the PATIENT confirmation authority.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from ..exceptions import InvalidStateTransition
from ..value_objects import (
    GlucoseValue,
    PatientConfirmationState,
    PhoneNumber,
    ReadingTag,
)
from .projections import PatientFacingGlucoseObservation


@dataclass
class GlucoseObservation:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    taken_at: datetime = field(default_factory=datetime.utcnow)
    value: GlucoseValue | None = None
    tag: ReadingTag | None = None
    confirmation: PatientConfirmationState = PatientConfirmationState.PENDING
    confirmed_by: PhoneNumber | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def confirm(self, by: PhoneNumber) -> None:
        if self.confirmation is not PatientConfirmationState.PENDING:
            raise InvalidStateTransition(
                f"observation cannot move {self.confirmation.value} -> confirmed"
            )
        self.confirmation = PatientConfirmationState.CONFIRMED
        self.confirmed_by = by

    def reject(self, by: PhoneNumber) -> None:
        if self.confirmation is not PatientConfirmationState.PENDING:
            raise InvalidStateTransition(
                f"observation cannot move {self.confirmation.value} -> rejected"
            )
        self.confirmation = PatientConfirmationState.REJECTED
        self.confirmed_by = by

    def to_patient_facing(self) -> PatientFacingGlucoseObservation:
        return PatientFacingGlucoseObservation(
            value_mg_dl=self.value.value_mg_dl if self.value else None,
            tag=self.tag.value if self.tag else None,
            taken_at=self.taken_at,
            confirmed=self.confirmation
            in {PatientConfirmationState.CONFIRMED, PatientConfirmationState.CORRECTED},
        )