"""Domain events (Gate 03)."""

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
]