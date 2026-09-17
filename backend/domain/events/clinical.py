"""Representative canonical clinical events (Gate 03).

A small, justified set of event vocabulary. Each event carries explicit
identity, timestamp, and (where appropriate) patient provenance. Only events
corresponding to existing domain behaviour are implemented.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from .base import DomainEvent


@dataclass(frozen=True)
class GlucoseObservationRecorded(DomainEvent):
    event_type: str = "glucose_observation.recorded"
    observation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class MealObservationRecorded(DomainEvent):
    event_type: str = "meal_observation.recorded"
    observation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class MealObservationConfirmed(DomainEvent):
    event_type: str = "meal_observation.confirmed"
    observation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class MedicationAdministrationRecorded(DomainEvent):
    event_type: str = "medication_administration.recorded"
    medication_plan_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CareTaskCreated(DomainEvent):
    event_type: str = "care_task.created"
    care_task_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CareTaskCompleted(DomainEvent):
    event_type: str = "care_task.completed"
    care_task_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AIArtifactGenerated(DomainEvent):
    event_type: str = "ai_artifact.generated"
    artifact_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AIArtifactReviewed(DomainEvent):
    event_type: str = "ai_artifact.reviewed"
    artifact_id: UUID = field(default_factory=uuid4)
    review_state: str = "approved"


@dataclass(frozen=True)
class PatientProvisioned(DomainEvent):
    event_type: str = "patient.provisioned"


@dataclass(frozen=True)
class CareTeamMemberProvisioned(DomainEvent):
    event_type: str = "care_team_member.provisioned"