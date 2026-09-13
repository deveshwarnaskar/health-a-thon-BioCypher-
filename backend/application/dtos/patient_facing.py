"""Patient-facing DTOs (Gate 04).

CRITICAL information-asymmetry boundary. The patient timeline carries ONLY
patient-facing projections produced by the domain (``to_patient_facing``).
Clinician-only analytical fields (carbohydrate grams, glycemic index) do not
exist on this shape.

The clinician feed in ``clinical.py`` is a SEPARATE type and is never returned
by patient-facing query handlers.
"""

from dataclasses import dataclass, field
from typing import Union

from ...domain.entities.projections import (
    PatientFacingGlucoseObservation,
    PatientFacingMealObservation,
)

PatientFacingItem = Union[PatientFacingMealObservation, PatientFacingGlucoseObservation]


@dataclass(frozen=True)
class PatientObservationFeed:
    patient_id: object
    items: list[PatientFacingItem] = field(default_factory=list)

    def to_dicts(self) -> list[dict]:
        """Plain serializable view used by patient-facing interfaces."""
        out: list[dict] = []
        for item in self.items:
            if isinstance(item, PatientFacingMealObservation):
                out.append(
                    {
                        "kind": "meal",
                        "description": item.description,
                        "portion_label": item.portion_label,
                        "quantity": item.quantity,
                        "recorded_at": item.recorded_at.isoformat(),
                        "confirmed": item.confirmed,
                    }
                )
            else:
                out.append(
                    {
                        "kind": "glucose",
                        "value_mg_dl": item.value_mg_dl,
                        "tag": item.tag,
                        "taken_at": item.taken_at.isoformat(),
                        "confirmed": item.confirmed,
                    }
                )
        return out