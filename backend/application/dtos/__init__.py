"""Data transfer objects (Gate 04).

Explicit application DTO boundaries. Patient-facing and clinician-facing shapes
are distinct types and never collapse into one universal DTO.
"""

from .caregiver import CaregiverAuthorizedPatient, CaregiverPatientList
from .clinical import (
    ClinicalGlucoseRecord,
    ClinicalMealRecord,
    ClinicalObservationFeed,
)
from .patient_facing import PatientObservationFeed
from .results import (
    AdministrationRecorded,
    AIArtifactGeneratedResult,
    AIArtifactReviewedResult,
    CareTaskCompletedResult,
    CareTaskCreatedResult,
    MealDraftAccepted,
    MealObservationConfirmedResult,
    MedicationPlanCreated,
    ObservationIngested,
    PhoneLinked,
)

__all__ = [
    "CaregiverAuthorizedPatient",
    "CaregiverPatientList",
    "ClinicalGlucoseRecord",
    "ClinicalMealRecord",
    "ClinicalObservationFeed",
    "PatientObservationFeed",
    "AdministrationRecorded",
    "AIArtifactGeneratedResult",
    "AIArtifactReviewedResult",
    "CareTaskCompletedResult",
    "CareTaskCreatedResult",
    "MealDraftAccepted",
    "MealObservationConfirmedResult",
    "MedicationPlanCreated",
    "ObservationIngested",
    "PhoneLinked",
]