"""Persistence repositories package (Gate 05).

Exports concrete SQLAlchemy repository implementations.
"""

from .patient_repo import SqlAlchemyPatientRepository
from .facility_repo import SqlAlchemyFacilityRepository
from .care_team_member_repo import SqlAlchemyCareTeamMemberRepository
from .caregiver_relationship_repo import SqlAlchemyCaregiverRelationshipRepository
from .identity_patient_mapping_repo import SqlAlchemyIdentityPatientMappingRepository
from .glucose_observation_repo import SqlAlchemyGlucoseObservationRepository
from .meal_observation_repo import SqlAlchemyMealObservationRepository
from .medication_plan_repo import SqlAlchemyMedicationPlanRepository
from .care_task_repo import SqlAlchemyCareTaskRepository
from .ai_artifact_repo import SqlAlchemyAIReviewArtifactRepository
from .notification_repo import SqlAlchemyNotificationRepository
from .document_reference_repo import SqlAlchemyDocumentReferenceRepository

__all__ = [
    "SqlAlchemyPatientRepository",
    "SqlAlchemyFacilityRepository",
    "SqlAlchemyCareTeamMemberRepository",
    "SqlAlchemyCaregiverRelationshipRepository",
    "SqlAlchemyIdentityPatientMappingRepository",
    "SqlAlchemyGlucoseObservationRepository",
    "SqlAlchemyMealObservationRepository",
    "SqlAlchemyMedicationPlanRepository",
    "SqlAlchemyCareTaskRepository",
    "SqlAlchemyAIReviewArtifactRepository",
    "SqlAlchemyNotificationRepository",
    "SqlAlchemyDocumentReferenceRepository",
]
