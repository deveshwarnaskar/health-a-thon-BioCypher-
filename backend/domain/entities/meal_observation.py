"""MealObservation entity (Gate 03).

Patient-originated meal extraction with the PATIENT confirmation authority.
Retains clinician-only analytic fields (carbohydrate grams, glycemic index) on
the clinical representation; patient-facing projections must NEVER expose them
(clinical information asymmetry — see ``projections.py``).
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from ..exceptions import InvalidStateTransition
from ..value_objects import MealPortion, PatientConfirmationState, PhoneNumber
from .projections import PatientFacingMealObservation

_CONFIRM_TRANSITIONS = {
    PatientConfirmationState.PENDING: {
        PatientConfirmationState.CONFIRMED,
        PatientConfirmationState.CORRECTED,
        PatientConfirmationState.REJECTED,
    },
    PatientConfirmationState.CONFIRMED: {PatientConfirmationState.CORRECTED},
}


@dataclass
class MealObservation:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    portion: MealPortion | None = None
    carbs_grams: float | None = None
    glycemic_index: str | None = None
    confirmation: PatientConfirmationState = PatientConfirmationState.PENDING
    confirmed_by: PhoneNumber | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def confirm(self, by: PhoneNumber) -> None:
        self._transition(PatientConfirmationState.CONFIRMED)
        self.confirmed_by = by

    def correct(self, description: str, portion: MealPortion | None) -> None:
        if self.confirmation is PatientConfirmationState.REJECTED:
            raise InvalidStateTransition("rejected observation cannot be corrected")
        self.description = description
        self.portion = portion
        self.confirmation = PatientConfirmationState.CORRECTED

    def reject(self, by: PhoneNumber) -> None:
        self._transition(PatientConfirmationState.REJECTED)
        self.confirmed_by = by

    def _transition(self, target: PatientConfirmationState) -> None:
        allowed = _CONFIRM_TRANSITIONS.get(self.confirmation)
        if allowed is None or target not in allowed:
            raise InvalidStateTransition(
                f"observation cannot move {self.confirmation.value} -> {target.value}"
            )
        self.confirmation = target

    def to_patient_facing(self) -> PatientFacingMealObservation:
        return PatientFacingMealObservation(
            description=self.description,
            portion_label=self.portion.katori.label if self.portion else None,
            quantity=self.portion.quantity if self.portion else None,
            recorded_at=self.recorded_at,
            confirmed=self.confirmation
            in {PatientConfirmationState.CONFIRMED, PatientConfirmationState.CORRECTED},
        )