"""Command contracts (Gate 04).

Input spells for application use cases. Frozen dataclasses; required input is
enforced by the shape (no ``Optional`` on required fields); domain value objects
carry structural validation.
"""

from .complete_care_task import CompleteCareTask
from .confirm_meal_observation import ConfirmMealObservation
from .create_care_task import CreateCareTask
from .create_medication_plan import CreateMedicationPlan
from .evaluate_escalations import EvaluateEscalations
from .generate_ai_review_artifact import GenerateAIReviewArtifact
from .ingest_glucose_reading import IngestGlucoseReading
from .link_patient_phone import LinkPatientPhone
from .log_meal_draft import LogMealDraft
from .record_medication_administration import RecordMedicationAdministration
from .review_ai_artifact import ReviewAIArtifact, ReviewDecision

__all__ = [
    "CompleteCareTask",
    "ConfirmMealObservation",
    "CreateCareTask",
    "CreateMedicationPlan",
    "EvaluateEscalations",
    "GenerateAIReviewArtifact",
    "IngestGlucoseReading",
    "LinkPatientPhone",
    "LogMealDraft",
    "RecordMedicationAdministration",
    "ReviewAIArtifact",
    "ReviewDecision",
]