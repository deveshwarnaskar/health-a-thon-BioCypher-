"""Gate 03 — Clinical information asymmetry.

CRITICAL invariant: patient-facing projections must never expose clinician-only
analytical fields such as carbohydrate grams or glycemic index.
"""

import dataclasses
from datetime import datetime, timezone
from uuid import uuid4

from backend.domain.entities import (
    GlucoseObservation,
    MealObservation,
    PatientFacingGlucoseObservation,
    PatientFacingMealObservation,
)
from backend.domain.value_objects import GlucoseValue, KatoriVolume, MealPortion


def _meal() -> MealObservation:
    return MealObservation(
        patient_id=uuid4(),
        recorded_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        description="2 roti and dal",
        portion=MealPortion(food_key="roti", katori=KatoriVolume(220), quantity=2.0),
        carbs_grams=44.5,
        glycemic_index="medium",
    )


def test_patient_facing_projection_has_no_carbohydrate_grams():
    proj = _meal().to_patient_facing()
    field_names = {f.name for f in dataclasses.fields(PatientFacingMealObservation)}
    assert "carbs_grams" not in field_names
    assert not hasattr(proj, "carbs_grams")


def test_patient_facing_projection_has_no_glycemic_index():
    proj = _meal().to_patient_facing()
    field_names = {f.name for f in dataclasses.fields(PatientFacingMealObservation)}
    assert "glycemic_index" not in field_names
    assert not hasattr(proj, "glycemic_index")


def test_clinical_observation_retains_clinician_only_fields():
    obs = _meal()
    assert obs.carbs_grams == 44.5
    assert obs.glycemic_index == "medium"


def test_patient_facing_projection_keeps_plain_meal_facts():
    proj = _meal().to_patient_facing()
    assert proj.description == "2 roti and dal"
    assert proj.portion_label == "medium"
    assert proj.quantity == 2.0
    assert proj.confirmed is False


def test_glucose_projection_exposes_value_but_no_analytics():
    obs = GlucoseObservation(
        patient_id=uuid4(),
        taken_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        value=GlucoseValue(140),
    )
    proj = obs.to_patient_facing()
    assert isinstance(proj, PatientFacingGlucoseObservation)
    assert proj.value_mg_dl == 140
    field_names = {f.name for f in dataclasses.fields(PatientFacingGlucoseObservation)}
    assert "carbs_grams" not in field_names
    assert "glycemic_index" not in field_names