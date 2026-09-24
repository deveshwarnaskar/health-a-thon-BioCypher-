"""DTO information asymmetry tests (Gate 07).

Patient-facing DTOs MUST NOT contain:
- carbohydrate grams
- glycemic index
- clinical nutrition analytics

Clinician-facing DTOs MAY contain them.

This is a cross-gate invariant enforced at the schema boundary.
"""

from __future__ import annotations

import pytest

from backend.interfaces.http.v2.schemas import (
    ClinicalMealObservationResponse,
    ClinicalObservationFeedResponse,
    PatientMealObservationResponse,
    PatientObservationFeedResponse,
    PatientGlucoseObservationResponse,
)


class TestPatientFacingDTOAsymmetry:
    """Patient-facing response schemas must not leak clinical analytics."""

    def test_patient_meal_no_carbs_grams(self):
        schema = PatientMealObservationResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "carbs_grams" not in props, (
            "PatientMealObservationResponse must NOT expose carbs_grams"
        )

    def test_patient_meal_no_glycemic_index(self):
        schema = PatientMealObservationResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "glycemic_index" not in props, (
            "PatientMealObservationResponse must NOT expose glycemic_index"
        )

    def test_patient_meal_no_nutrition_analytics(self):
        """No macronutrient or nutrition analytics fields."""
        schema = PatientMealObservationResponse.model_json_schema()
        props = set(schema.get("properties", {}).keys())
        forbidden = {"carbs_grams", "glycemic_index", "macronutrient", "calories", "gi_score"}
        leaked = props & forbidden
        assert not leaked, f"Patient DTO leaks: {leaked}"

    def test_patient_glucose_no_clinical_interpretation(self):
        schema = PatientGlucoseObservationResponse.model_json_schema()
        props = set(schema.get("properties", {}).keys())
        forbidden = {"hba1c_equivalent", "risk_score", "interpretation", "carbs_grams"}
        leaked = props & forbidden
        assert not leaked, f"Patient glucose DTO leaks: {leaked}"

    def test_patient_feed_no_carbs_in_serialization(self):
        """PatientObservationFeedResponse.to_dicts() never includes carbs."""
        # Verify the schema itself has no carbs path
        schema = PatientObservationFeedResponse.model_json_schema()
        schema_str = str(schema)
        assert "carbs_grams" not in schema_str
        assert "glycemic_index" not in schema_str


class TestClinicianDTOAsymmetry:
    """Clinician-facing schemas MAY expose clinical analytics."""

    def test_clinician_meal_has_carbs_grams(self):
        schema = ClinicalMealObservationResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "carbs_grams" in props

    def test_clinician_meal_has_glycemic_index(self):
        schema = ClinicalMealObservationResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "glycemic_index" in props

    def test_clinician_meal_has_observation_id(self):
        schema = ClinicalMealObservationResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "observation_id" in props


class TestStrictRequestSchemas:
    """Request schemas must reject unknown fields (tenant spoofing prevention)."""

    def test_ingest_glucose_rejects_unknown_field(self):
        from backend.interfaces.http.v2.schemas import IngestGlucoseRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            IngestGlucoseRequest.model_validate(
                {"patient_id": "12345678-1234-1234-1234-123456789abc", "value_mg_dl": 150, "tenant_id": "X"}
            )

    def test_create_medication_plan_rejects_prescriber_override(self):
        from backend.interfaces.http.v2.schemas import CreateMedicationPlanRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CreateMedicationPlanRequest.model_validate(
                {
                    "patient_id": "12345678-1234-1234-1234-123456789abc",
                    "medication": "Metformin",
                    "prescribed_by_user_id": str(__import__("uuid").uuid4()),
                }
            )

    def test_review_artifact_rejects_reviewer_override(self):
        from backend.interfaces.http.v2.schemas import ReviewAIArtifactRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ReviewAIArtifactRequest.model_validate(
                {
                    "decision": "approve",
                    "reviewer_user_id": str(__import__("uuid").uuid4()),
                }
            )

    def test_create_notification_rejects_unknown_field(self):
        from backend.interfaces.http.v2.schemas import CreateNotificationRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CreateNotificationRequest.model_validate(
                {
                    "recipient_id": "12345678-1234-1234-1234-123456789abc",
                    "recipient_phone": "+919876543210",
                    "template_name": "reminder",
                    "tenant_id": "malicious-tenant-injection",
                }
            )


class TestNotificationDTOAsymmetry:
    """Notification response schemas must never leak clinical analytical fields."""

    def test_notification_response_no_carbs_grams(self):
        from backend.interfaces.http.v2.schemas import NotificationResponse
        schema = NotificationResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "carbs_grams" not in props
        assert "glycemic_index" not in props
        assert "risk_score" not in props
        assert "ai_diagnosis" not in props
