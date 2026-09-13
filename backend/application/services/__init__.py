"""Application services (Gate 04).

Use-case orchestration. Handlers depend only on command/query contracts, the
domain, and application ports. Infrastructure implementations are injected
through ports; they are never imported here.
"""

from .complete_care_task import CompleteCareTaskHandler
from .confirm_meal_observation import ConfirmMealObservationHandler
from .create_care_task import CreateCareTaskHandler
from .create_medication_plan import CreateMedicationPlanHandler
from .generate_ai_artifact import GenerateAIReviewArtifactHandler
from .get_clinical_observation_feed import GetClinicalObservationFeedHandler
from .get_patient_observation_feed import GetPatientObservationFeedHandler
from .ingest_glucose import IngestGlucoseHandler
from .link_patient_phone import LinkPatientPhoneHandler
from .log_meal_draft import LogMealDraftHandler
from .record_medication_administration import RecordMedicationAdministrationHandler
from .review_ai_artifact import ReviewAIArtifactHandler

__all__ = [
    "CompleteCareTaskHandler",
    "ConfirmMealObservationHandler",
    "CreateCareTaskHandler",
    "CreateMedicationPlanHandler",
    "GenerateAIReviewArtifactHandler",
    "GetClinicalObservationFeedHandler",
    "GetPatientObservationFeedHandler",
    "IngestGlucoseHandler",
    "LinkPatientPhoneHandler",
    "LogMealDraftHandler",
    "RecordMedicationAdministrationHandler",
    "ReviewAIArtifactHandler",
]