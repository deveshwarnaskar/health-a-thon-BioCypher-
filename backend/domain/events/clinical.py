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
    # Provenance of how the reading was produced (e.g. voice transcript metadata)
    source_metadata: dict | None = field(default=None)


@dataclass(frozen=True)
class MealObservationRecorded(DomainEvent):
    event_type: str = "meal_observation.recorded"
    observation_id: UUID = field(default_factory=uuid4)
    # Provenance of how the meal draft was produced (voice/image/typed + provider)
    source_metadata: dict | None = field(default=None)


@dataclass(frozen=True)
class MealObservationConfirmed(DomainEvent):
    event_type: str = "meal_observation.confirmed"
    observation_id: UUID = field(default_factory=uuid4)
    # Provenance threaded through from the draft + confirm medium (button/text)
    source_metadata: dict | None = field(default=None)


@dataclass(frozen=True)
class GlucoseObservationConfirmed(DomainEvent):
    event_type: str = "glucose_observation.confirmed"
    observation_id: UUID = field(default_factory=uuid4)
    source_metadata: dict | None = field(default=None)


@dataclass(frozen=True)
class MedicationAdministrationRecorded(DomainEvent):
    event_type: str = "medication_administration.recorded"
    medication_plan_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CareTaskCreated(DomainEvent):
    event_type: str = "care_task.created"
    care_task_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CareTaskStarted(DomainEvent):
    event_type: str = "care_task.started"
    care_task_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CareTaskCompleted(DomainEvent):
    event_type: str = "care_task.completed"
    care_task_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CareTaskReassigned(DomainEvent):
    event_type: str = "care_task.reassigned"
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


@dataclass(frozen=True)
class ClinicalReportGenerated(DomainEvent):
    event_type: str = "clinical_report.generated"
    document_id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)