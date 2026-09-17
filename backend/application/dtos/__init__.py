"""Data transfer objects (Gate 04).

Explicit application DTO boundaries. Patient-facing and clinician-facing shapes
are distinct types and never collapse into one universal DTO.
"""

from .admin import (
    AdminPatientListResult,
    AdminPatientSummaryResult,
    CareTeamMemberListResult,
    CareTeamMemberResult,
    FacilityListResult,
    FacilityResult,
)
from .caregiver import CaregiverAuthorizedPatient, CaregiverPatientList
from .clinical import (
    ClinicalGlucoseRecord,
    ClinicalMealRecord,
    ClinicalObservationFeed,
)
from .clinician_reads import (
    AIReviewArtifactList,
    AIReviewArtifactRecord,
    MedicationPlanList,
    MedicationPlanRecord,
    PatientList,
    PatientRecord,
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
    "AdministrationRecorded",
    "AdminPatientListResult",
    "AdminPatientSummaryResult",
    "AIArtifactGeneratedResult",
    "AIArtifactReviewedResult",
    "AIReviewArtifactList",
    "AIReviewArtifactRecord",
    "CareTaskCompletedResult",
    "CareTaskCreatedResult",
    "CareTeamMemberListResult",
    "CareTeamMemberResult",
    "CaregiverAuthorizedPatient",
    "CaregiverPatientList",
    "ClinicalGlucoseRecord",
    "ClinicalMealRecord",
    "ClinicalObservationFeed",
    "FacilityListResult",
    "FacilityResult",
    "MedicationPlanCreated",
    "MedicationPlanList",
    "MedicationPlanRecord",
    "MealDraftAccepted",
    "MealObservationConfirmedResult",
    "ObservationIngested",
    "PatientList",
    "PatientObservationFeed",
    "PatientRecord",
    "PhoneLinked",
]