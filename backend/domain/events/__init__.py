"""Domain events (Gate 03)."""

from .admin import (
    CareTeamMemberDeactivated,
    CareTeamMemberUpdated,
    FacilityCreated,
    FacilityDeactivated,
    FacilityUpdated,
    PatientDeactivated,
)
from .base import DomainEvent
from .channel import ChannelMessageQueued
from .clinical import (
    AIArtifactGenerated,
    AIArtifactReviewed,
    CareTaskCompleted,
    CareTaskCreated,
    CareTaskReassigned,
    CareTaskStarted,
    CareTeamMemberProvisioned,
    ClinicalReportGenerated,
    GlucoseObservationConfirmed,
    GlucoseObservationRecorded,
    MealObservationConfirmed,
    MealObservationRecorded,
    MedicationAdministrationRecorded,
    PatientProvisioned,
)
from .identity import (
    CaregiverRelationshipCreated,
    CaregiverRelationshipExpired,
    CaregiverRelationshipRevoked,
    CaregiverRelationshipVerified,
    IdentityMappingCreated,
    IdentityMappingDeactivated,
)

__all__ = [
    "DomainEvent",
    "ChannelMessageQueued",
    "GlucoseObservationRecorded",
    "GlucoseObservationConfirmed",
    "MealObservationRecorded",
    "MealObservationConfirmed",
    "MedicationAdministrationRecorded",
    "CareTaskCreated",
    "CareTaskStarted",
    "CareTaskReassigned",
    "CareTaskCompleted",
    "AIArtifactGenerated",
    "AIArtifactReviewed",
    "IdentityMappingCreated",
    "IdentityMappingDeactivated",
    "CaregiverRelationshipCreated",
    "CaregiverRelationshipVerified",
    "CaregiverRelationshipRevoked",
    "CaregiverRelationshipExpired",
    "PatientProvisioned",
    "CareTeamMemberProvisioned",
    "ClinicalReportGenerated",
    "FacilityCreated",
    "FacilityUpdated",
    "FacilityDeactivated",
    "CareTeamMemberUpdated",
    "CareTeamMemberDeactivated",
    "PatientDeactivated",
]