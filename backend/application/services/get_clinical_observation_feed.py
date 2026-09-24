"""GetClinicalObservationFeed query handler (Gate 04).

CLINICIAN-ONLY. Returns clinical records that include clinician-only analytical
fields. Intentionally a separate DTO from the patient-facing feed; authorized
clinician workflows (P.L.A.T.E., Phase 2) receive this type, patient endpoints
never do. Interface-level RBAC enforcement is deferred to the interfaces gate.
"""

from datetime import datetime

from ..dtos.clinical import (
    ClinicalGlucoseRecord,
    ClinicalMealRecord,
    ClinicalObservationFeed,
)
from ..ports.unit_of_work import UnitOfWork
from ..queries import GetClinicalObservationFeed


class GetClinicalObservationFeedHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def handle(self, q: GetClinicalObservationFeed) -> ClinicalObservationFeed:
        meals = self._uow.meal_observations.list_for_patient(q.patient_id)
        glucose = self._uow.glucose_observations.list_for_patient(q.patient_id)
        stamped: list[tuple[datetime, object]] = []
        for m in meals:
            stamped.append(
                (
                    m.recorded_at,
                    ClinicalMealRecord(
                        observation_id=m.id,
                        description=m.description,
                        portion_label=m.portion.katori.label if m.portion else None,
                        quantity=m.portion.quantity if m.portion else None,
                        carbs_grams=m.carbs_grams,
                        glycemic_index=m.glycemic_index,
                        recorded_at=m.recorded_at,
                        confirmation=m.confirmation.value,
                    ),
                )
            )
        for g in glucose:
            stamped.append(
                (
                    g.taken_at,
                    ClinicalGlucoseRecord(
                        observation_id=g.id,
                        value_mg_dl=g.value.value_mg_dl if g.value else None,
                        tag=g.tag.value if g.tag else None,
                        taken_at=g.taken_at,
                        confirmation=g.confirmation.value,
                    ),
                )
            )
        stamped.sort(key=lambda pair: pair[0], reverse=True)
        return ClinicalObservationFeed(
            patient_id=q.patient_id,
            items=[item for _, item in stamped[: q.limit]],
        )