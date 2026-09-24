"""Domain entities (Gate 03 production contracts)."""

from .ai_artifact import AIReviewArtifact, ReviewAuthority, ReviewState
from .care_team_member import CareTeamMember, CareTeamRole
from .care_task import CareTask, CareTaskStatus
from .caregiver_relationship import CaregiverRelationship, CaregiverRelationshipStatus
from .document_reference import DocumentKind, DocumentReference
from .facility import Facility
from .identity_patient_mapping import IdentityPatientMapping
from .glucose_observation import GlucoseObservation
from .meal_observation import MealObservation
from .clinical_observation import ClinicalObservation, ObservationType
from .medication_plan import MedicationPlan
from .notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from .patient import Patient
from .patient_clinician_link import PatientClinicianLink
from .projections import (
    PatientFacingGlucoseObservation,
    PatientFacingMealObservation,
)

__all__ = [
    "AIReviewArtifact",
    "ReviewAuthority",
    "ReviewState",
    "CareTeamMember",
    "CareTeamRole",
    "CareTask",
    "CareTaskStatus",
    "CaregiverRelationship",
    "CaregiverRelationshipStatus",
    "DocumentKind",
    "DocumentReference",
    "Facility",
    "IdentityPatientMapping",
    "GlucoseObservation",
    "MealObservation",
    "ClinicalObservation",
    "ObservationType",
    "MedicationPlan",
    "Notification",
    "NotificationChannel",
    "NotificationStatus",
    "NotificationType",
    "Patient",
    "PatientClinicianLink",
    "PatientFacingGlucoseObservation",
    "PatientFacingMealObservation",
]