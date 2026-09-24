"""Relational identity events (Gate 08).

Canonical events for identity-patient mappings and caregiver relationships.
They are published through the existing ``DomainEventPublisher``/outbox
mechanism — persistent audit infrastructure remains a Gate 09 concern.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from .base import DomainEvent


@dataclass(frozen=True)
class IdentityMappingCreated(DomainEvent):
    event_type: str = "identity_mapping.created"
    mapping_id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class IdentityMappingDeactivated(DomainEvent):
    event_type: str = "identity_mapping.deactivated"
    mapping_id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CaregiverRelationshipCreated(DomainEvent):
    event_type: str = "caregiver_relationship.created"
    relationship_id: UUID = field(default_factory=uuid4)
    caregiver_user_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CaregiverRelationshipVerified(DomainEvent):
    event_type: str = "caregiver_relationship.verified"
    relationship_id: UUID = field(default_factory=uuid4)
    caregiver_user_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CaregiverRelationshipRevoked(DomainEvent):
    event_type: str = "caregiver_relationship.revoked"
    relationship_id: UUID = field(default_factory=uuid4)
    caregiver_user_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CaregiverRelationshipExpired(DomainEvent):
    event_type: str = "caregiver_relationship.expired"
    relationship_id: UUID = field(default_factory=uuid4)
    caregiver_user_id: UUID = field(default_factory=uuid4)