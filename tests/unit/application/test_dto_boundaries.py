"""Gate 04 — patient vs clinician DTO boundaries.

Patient-facing projections/DTOs must never expose clinician-only analytics
(carbohydrate grams, glycemic index, restricted synthesis). The patient feed
and the clinician feed are distinct types that never collapse into one
unrestricted DTO.
"""

import dataclasses
from uuid import uuid4

from backend.application.commands import ConfirmMealObservation, LogMealDraft
from backend.application.dtos.clinical import (
    ClinicalGlucoseRecord,
    ClinicalMealRecord,
    ClinicalObservationFeed,
)
from backend.application.dtos.patient_facing import PatientObservationFeed
from backend.application.queries import (
    GetClinicalObservationFeed,
    GetPatientObservationFeed,
)
from backend.domain.entities import (
    GlucoseObservation,
    MealObservation,
    PatientFacingMealObservation,
)
from backend.domain.value_objects import (
    GlucoseValue,
    KatoriVolume,
    MealPortion,
    PhoneNumber,
)


def _seed_clinical_glucose(uow, patient_id, value=140):
    obs = GlucoseObservation(patient_id=patient_id, value=GlucoseValue(value))
    uow.glucose_observations.add(obs)
    return obs


def _seed_clinical_meal(uow, patient_id):
    obs = MealObservation(
        patient_id=patient_id,
        description="2 roti and dal",
        portion=MealPortion(food_key="roti", katori=KatoriVolume(220), quantity=2.0),
        carbs_grams=44.5,
        glycemic_index="medium",
    )
    uow.meal_observations.add(obs)
    return obs


def test_patient_feed_serializes_without_clinical_analytics(world):
    uow, app, patient_id = world["uow"], world["app"], world["patient_id"]
    _seed_clinical_meal(uow, patient_id)

    feed = app.patient_feed.handle(GetPatientObservationFeed(patient_id=patient_id))

    assert isinstance(feed, PatientObservationFeed)
    assert len(feed.items) == 1
    item = feed.items[0]
    assert isinstance(item, PatientFacingMealObservation)
    field_names = {f.name for f in dataclasses.fields(PatientFacingMealObservation)}
    assert "carbs_grams" not in field_names
    assert "glycemic_index" not in field_names

    serialized = feed.to_dicts()[0]
    assert "carbs_grams" not in serialized
    assert "glycemic_index" not in serialized
    assert serialized["description"] == "2 roti and dal"


def test_clinical_feed_is_distinct_type_with_clinician_fields(world):
    uow, app, patient_id = world["uow"], world["app"], world["patient_id"]
    _seed_clinical_meal(uow, patient_id)

    feed = app.clinical_feed.handle(
        GetClinicalObservationFeed(patient_id=patient_id, clinician_user_id=world["doctor_user_id"])
    )

    assert isinstance(feed, ClinicalObservationFeed)
    item = feed.items[0]
    assert isinstance(item, ClinicalMealRecord)
    assert item.carbs_grams == 44.5
    assert item.glycemic_index == "medium"
    diabetes = isinstance(item, ClinicalMealRecord)
    assert diabetes


def test_patient_and_clinical_feed_types_never_collapse(world):
    assert ClinicalObservationFeed is not PatientObservationFeed
    assert ClinicalMealRecord is not PatientFacingMealObservation
    # a single record cannot be both shapes
    meal_fields = {f.name for f in dataclasses.fields(PatientFacingMealObservation)}
    clinical_fields = {f.name for f in dataclasses.fields(ClinicalMealRecord)}
    assert not meal_fields.issubset(clinical_fields) or clinical_fields != meal_fields
    assert clinical_fields.issuperset(meal_fields & {"description"})
    assert {"carbs_grams", "glycemic_index"}.issubset(clinical_fields)


def test_glucose_clinical_record_keeps_glycemic_context(world):
    uow, app, patient_id = world["uow"], world["app"], world["patient_id"]
    reading = _seed_clinical_glucose(uow, patient_id)

    feed = app.clinical_feed.handle(
        GetClinicalObservationFeed(patient_id=patient_id, clinician_user_id=world["doctor_user_id"])
    )
    record = feed.items[0]
    assert isinstance(record, ClinicalGlucoseRecord)
    assert record.observation_id == reading.id
    assert record.value_mg_dl == 140


def test_patient_feed_never_returns_clinical_type(world):
    uow, app, patient_id = world["uow"], world["app"], world["patient_id"]
    _seed_clinical_meal(uow, patient_id)
    _seed_clinical_glucose(uow, patient_id)

    feed = app.patient_feed.handle(GetPatientObservationFeed(patient_id=patient_id))
    for item in feed.items:
        assert not isinstance(item, (ClinicalMealRecord, ClinicalGlucoseRecord))
    assert all(isinstance(i, (PatientFacingMealObservation,)) or hasattr(i, "value_mg_dl") for i in feed.items)


def test_patient_flow_confirms_meal_and_projection_stays_plain(world):
    app, patient_id = world["app"], world["patient_id"]
    draft = app.log_meal_draft.handle(
        LogMealDraft(patient_id=patient_id, description="dal and rice", recorded_at=world["clock"].now())
    )
    app.confirm_meal_observation.handle(
        ConfirmMealObservation(
            meal_observation_id=draft.meal_observation_id,
            confirmed_by=PhoneNumber("+919000000001"),
        )
    )

    feed = app.patient_feed.handle(GetPatientObservationFeed(patient_id=patient_id))
    item = feed.items[0]
    assert item.confirmed is True
    serialized = feed.to_dicts()[0]
    assert serialized["kind"] == "meal"
    assert "carbs_grams" not in serialized