"""Port contracts (Gate 04).

Outbound ports express WHAT the application requires from the outside world.
Each port is justified by a current use case, or is a retained scaffold
boundary reserved for a documented later gate (notifications/reporting/object
storage). Infrastructure implementations arrive with the infrastructure gate.
"""

from .ai import AIArtifactGenerator, ArtifactDraft
from .clock import Clock
from .events import DomainEventPublisher
from .id_generation import IdGenerator
from .notifications import INotificationSender
from .reporting import IDocumentRenderer
from .repositories import (
    AIReviewArtifactRepository,
    CareTaskRepository,
    CareTeamMemberRepository,
    GlucoseObservationRepository,
    MealObservationRepository,
    MedicationPlanRepository,
    PatientRepository,
)
from .storage import IObjectStorage
from .unit_of_work import UnitOfWork

__all__ = [
    "AIArtifactGenerator",
    "ArtifactDraft",
    "Clock",
    "DomainEventPublisher",
    "IdGenerator",
    "INotificationSender",
    "IDocumentRenderer",
    "IObjectStorage",
    "PatientRepository",
    "CareTeamMemberRepository",
    "GlucoseObservationRepository",
    "MealObservationRepository",
    "MedicationPlanRepository",
    "CareTaskRepository",
    "AIReviewArtifactRepository",
    "UnitOfWork",
]