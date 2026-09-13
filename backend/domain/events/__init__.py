"""Domain events (Gate 03)."""

from .base import DomainEvent
from .clinical import (
    AIArtifactGenerated,
    AIArtifactReviewed,
    CareTaskCompleted,
    CareTaskCreated,
    GlucoseObservationRecorded,
    MealObservationConfirmed,
    MealObservationRecorded,
    MedicationAdministrationRecorded,
)

__all__ = [
    "DomainEvent",
    "GlucoseObservationRecorded",
    "MealObservationRecorded",
    "MealObservationConfirmed",
    "MedicationAdministrationRecorded",
    "CareTaskCreated",
    "CareTaskCompleted",
    "AIArtifactGenerated",
    "AIArtifactReviewed",
]