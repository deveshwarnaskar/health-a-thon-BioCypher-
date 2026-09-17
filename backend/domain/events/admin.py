"""Administrative domain events (Gate 10K-B)."""

from dataclasses import dataclass
from uuid import UUID

from .base import DomainEvent


@dataclass(frozen=True)
class FacilityCreated(DomainEvent):
    event_type: str = "facility.created"
    facility_id: UUID | None = None


@dataclass(frozen=True)
class FacilityUpdated(DomainEvent):
    event_type: str = "facility.updated"
    facility_id: UUID | None = None


@dataclass(frozen=True)
class FacilityDeactivated(DomainEvent):
    event_type: str = "facility.deactivated"
    facility_id: UUID | None = None


@dataclass(frozen=True)
class CareTeamMemberUpdated(DomainEvent):
    event_type: str = "care_team_member.updated"
    member_id: UUID | None = None


@dataclass(frozen=True)
class CareTeamMemberDeactivated(DomainEvent):
    event_type: str = "care_team_member.deactivated"
    member_id: UUID | None = None


@dataclass(frozen=True)
class PatientDeactivated(DomainEvent):
    event_type: str = "patient.deactivated"
    patient_id: UUID | None = None

