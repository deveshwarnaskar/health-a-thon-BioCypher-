"""Domain events (Gate 03)."""

from .base import DomainEvent
from .channel import ChannelMessageQueued
from .clinical import (
    AIArtifactGenerated,
    AIArtifactReviewed,
    CareTaskCompleted,
    CareTaskCreated,
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