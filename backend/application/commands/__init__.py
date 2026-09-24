"""Command contracts (Gate 04).

Input spells for application use cases. Frozen dataclasses; required input is
enforced by the shape (no ``Optional`` on required fields); domain value objects
carry structural validation.
"""

from .add_care_team_member import AddCareTeamMember
from .admin_deactivate_patient import AdminDeactivatePatient
from .complete_care_task import CompleteCareTask
from .confirm_meal_observation import ConfirmMealObservation
from .confirm_glucose_observation import ConfirmGlucoseObservation
from .create_care_task import CreateCareTask
from .create_facility import CreateFacility
from .create_identity_mapping import CreateIdentityMapping
from .create_medication_plan import CreateMedicationPlan
from .create_patient import CreatePatient
from .deactivate_care_team_member import DeactivateCareTeamMember
from .deactivate_facility import DeactivateFacility
from .deactivate_identity_mapping import DeactivateIdentityMapping
from .evaluate_escalations import EvaluateEscalations
from .generate_ai_review_artifact import GenerateAIReviewArtifact
from .generate_report import GenerateReport
from .ingest_glucose_reading import IngestGlucoseReading
from .link_patient_phone import LinkPatientPhone
from .log_meal_draft import LogMealDraft
from .record_medication_administration import RecordMedicationAdministration
from .register_caregiver_relationship import RegisterCaregiverRelationship
from .reassign_care_task import ReassignCareTask
from .revoke_caregiver_relationship import RevokeCaregiverRelationship
from .review_ai_artifact import ReviewAIArtifact, ReviewDecision
from .start_care_task import StartCareTask
from .update_care_team_member import UpdateCareTeamMember
from .update_facility import UpdateFacility
from .upload_document import UploadDocument
from .verify_caregiver_relationship import VerifyCaregiverRelationship

__all__ = [
    "AddCareTeamMember",
    "AdminDeactivatePatient",
    "CompleteCareTask",
    "ConfirmMealObservation",
    "ConfirmGlucoseObservation",
    "CreateCareTask",
    "CreateFacility",
    "CreateIdentityMapping",
    "CreateMedicationPlan",
    "CreatePatient",
    "DeactivateCareTeamMember",
    "DeactivateFacility",
    "DeactivateIdentityMapping",
    "EvaluateEscalations",
    "GenerateAIReviewArtifact",
    "GenerateReport",
    "IngestGlucoseReading",
    "LinkPatientPhone",
    "LogMealDraft",
    "RecordMedicationAdministration",
    "ReassignCareTask",
    "RegisterCaregiverRelationship",
    "RevokeCaregiverRelationship",
    "ReviewAIArtifact",
    "ReviewDecision",
    "StartCareTask",
    "UpdateCareTeamMember",
    "UpdateFacility",
    "UploadDocument",
    "VerifyCaregiverRelationship",
]