"""Application services (Gate 04).

Use-case orchestration. Handlers depend only on command/query contracts, the
domain, and application ports. Infrastructure implementations are injected
through ports; they are never imported here.
"""

from .complete_care_task import CompleteCareTaskHandler
from .confirm_meal_observation import ConfirmMealObservationHandler
from .create_care_task import CreateCareTaskHandler
from .create_identity_mapping import CreateIdentityMappingHandler
from .create_medication_plan import CreateMedicationPlanHandler
from .deactivate_identity_mapping import DeactivateIdentityMappingHandler
from .generate_ai_artifact import GenerateAIReviewArtifactHandler
from .get_ai_review_artifact import GetAIReviewArtifactHandler
from .get_clinical_observation_feed import GetClinicalObservationFeedHandler
from .get_medication_plan import GetMedicationPlanHandler
from .get_patient import GetPatientHandler
from .get_patient_observation_feed import GetPatientObservationFeedHandler
from .identity_patient_resolver import IdentityPatientResolver, ResolvedPatientAccess
from .ingest_glucose import IngestGlucoseHandler
from .link_patient_phone import LinkPatientPhoneHandler
from .list_ai_review_artifacts import ListAIReviewArtifactsHandler
from .list_caregiver_patients import ListCaregiverPatientsHandler
from .list_medication_plans import ListMedicationPlansHandler
from .list_patients import ListPatientsHandler
from .log_meal_draft import LogMealDraftHandler
from .record_medication_administration import RecordMedicationAdministrationHandler
from .register_caregiver import RegisterCaregiverHandler
from .review_ai_artifact import ReviewAIArtifactHandler
from .revoke_caregiver import RevokeCaregiverHandler
from .verify_caregiver import VerifyCaregiverHandler

__all__ = [
    "CompleteCareTaskHandler",
    "ConfirmMealObservationHandler",
    "CreateCareTaskHandler",
    "CreateIdentityMappingHandler",
    "CreateMedicationPlanHandler",
    "DeactivateIdentityMappingHandler",
    "GenerateAIReviewArtifactHandler",
    "GetAIReviewArtifactHandler",
    "GetClinicalObservationFeedHandler",
    "GetMedicationPlanHandler",
    "GetPatientHandler",
    "GetPatientObservationFeedHandler",
    "IdentityPatientResolver",
    "ResolvedPatientAccess",
    "IngestGlucoseHandler",
    "LinkPatientPhoneHandler",
    "ListAIReviewArtifactsHandler",
    "ListCaregiverPatientsHandler",
    "ListMedicationPlansHandler",
    "ListPatientsHandler",
    "LogMealDraftHandler",
    "RecordMedicationAdministrationHandler",
    "RegisterCaregiverHandler",
    "ReviewAIArtifactHandler",
    "RevokeCaregiverHandler",
    "VerifyCaregiverHandler",
]