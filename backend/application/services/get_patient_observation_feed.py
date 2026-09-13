"""GetPatientObservationFeed query handler (Gate 04).

Returns ONLY patient-facing projections; the patient information boundary is
guaranteed by construction (domain ``to_patient_facing`` shapes have no
clinician-only fields).
"""

from datetime import datetime

from ..dtos.patient_facing import PatientObservationFeed
from ..ports.unit_of_work import UnitOfWork
from ..queries import GetPatientObservationFeed
from ...domain.entities.projections import (
    PatientFacingGlucoseObservation,
    PatientFacingMealObservation,
)


class GetPatientObservationFeedHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, q: GetPatientObservationFeed) -> PatientObservationFeed:
        meals = self._uow.meal_observations.list_for_patient(q.patient_id)
        glucose = self._uow.glucose_observations.list_for_patient(q.patient_id)
        stamped: list[tuple[datetime, PatientFacingMealObservation | PatientFacingGlucoseObservation]] = []
        for meal in meals:
            stamped.append((meal.recorded_at, meal.to_patient_facing()))
        for reading in glucose:
            stamped.append((reading.taken_at, reading.to_patient_facing()))
        stamped.sort(key=lambda pair: pair[0], reverse=True)
        return PatientObservationFeed(
            patient_id=q.patient_id,
            items=[item for _, item in stamped[: q.limit]],
        )