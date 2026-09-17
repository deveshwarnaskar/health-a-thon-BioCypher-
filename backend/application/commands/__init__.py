"""Command contracts (Gate 04).

Input spells for application use cases. Frozen dataclasses; required input is
enforced by the shape (no ``Optional`` on required fields); domain value objects
carry structural validation.
"""

from .add_care_team_member import AddCareTeamMember
from .complete_care_task import CompleteCareTask
from .confirm_meal_observation import ConfirmMealObservation
from .create_care_task import CreateCareTask
from .create_identity_mapping import CreateIdentityMapping
from .create_medication_plan import CreateMedicationPlan
from .create_patient import CreatePatient
from .deactivate_identity_mapping import DeactivateIdentityMapping
from .evaluate_escalations import EvaluateEscalations
from .generate_ai_review_artifact import GenerateAIReviewArtifact
from .ingest_glucose_reading import IngestGlucoseReading
from .link_patient_phone import LinkPatientPhone
from .log_meal_draft import LogMealDraft
from .record_medication_administration import RecordMedicationAdministration
from .register_caregiver_relationship import RegisterCaregiverRelationship
from .revoke_caregiver_relationship import RevokeCaregiverRelationship
from .review_ai_artifact import ReviewAIArtifact, ReviewDecision
from .verify_caregiver_relationship import VerifyCaregiverRelationship

__all__ = [
    "AddCareTeamMember",
    "CompleteCareTask",
    "ConfirmMealObservation",
    "CreateCareTask",
    "CreateIdentityMapping",
    "CreateMedicationPlan",
    "CreatePatient",
    "DeactivateIdentityMapping",
    "EvaluateEscalations",
    "GenerateAIReviewArtifact",
    "IngestGlucoseReading",
    "LinkPatientPhone",
    "LogMealDraft",
    "RecordMedicationAdministration",
    "RegisterCaregiverRelationship",
    "RevokeCaregiverRelationship",
    "ReviewAIArtifact",
    "ReviewDecision",
    "VerifyCaregiverRelationship",
]