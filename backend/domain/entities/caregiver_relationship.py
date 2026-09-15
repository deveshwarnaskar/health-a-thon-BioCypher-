"""CaregiverRelationship entity (Gate 03, extended Gate 08).

Patient-to-caregiver proxy authorization with an explicit relationship label
and a canonical status lifecycle:

    PENDING → VERIFIED → REVOKED
              VERIFIED → EXPIRED

Authorization (enforced by the authorization policy) requires:

    status == VERIFIED
    AND (expires_at IS NULL OR expires_at > now)

There is deliberately NO persistent ``active`` flag — ``active`` is a derived
read-only property that tracks ``status == VERIFIED``. Expired relationships
deny at authorization time even before the row is physically marked expired.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from ..exceptions import InvalidRelationship, InvalidStateTransition


class CaregiverRelationshipStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass
class CaregiverRelationship:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    caregiver_user_id: UUID = field(default_factory=uuid4)
    relationship: str = ""
    status: CaregiverRelationshipStatus = CaregiverRelationshipStatus.PENDING
    capabilities: frozenset[str] = field(default_factory=frozenset)
    verified_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not isinstance(self.relationship, str) or not self.relationship.strip():
            raise InvalidRelationship("caregiver relationship label is required")
        if not isinstance(self.capabilities, frozenset):
            object.__setattr__(self, "capabilities", frozenset(self.capabilities or []))

    @property
    def active(self) -> bool:
        """Derived activity: only a VERIFIED relationship grants access.

        Never persisted. Expiration is enforced against ``expires_at`` at
        authorization time, not through this flag.
        """
        return self.status is CaregiverRelationshipStatus.VERIFIED

    def has_capabilities(self, required: frozenset[str]) -> bool:
        """Return True when every token in ``required`` is granted."""
        if not required:
            return True
        return required.issubset(self.capabilities)

    def is_granted_at(self, now: datetime) -> bool:
        """Authorization-time grant check: VERIFIED and not expired.

        Expiration is enforced HERE, at authorization time, even though the
        physical ``expired`` transition may be processed asynchronously.
        """
        if self.status is not CaregiverRelationshipStatus.VERIFIED:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True

    def verify(self, verified_at: datetime | None = None) -> None:
        if self.status is not CaregiverRelationshipStatus.PENDING:
            raise InvalidStateTransition(
                f"cannot verify caregiver relationship in state {self.status.value}"
            )
        self.status = CaregiverRelationshipStatus.VERIFIED
        self.verified_at = verified_at or datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def revoke(self) -> None:
        if self.status is CaregiverRelationshipStatus.REVOKED:
            raise InvalidRelationship("caregiver relationship is already revoked")
        self.status = CaregiverRelationshipStatus.REVOKED
        self.revoked_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def expire(self, expired_at: datetime | None = None) -> None:
        if self.status is CaregiverRelationshipStatus.REVOKED:
            raise InvalidStateTransition(
                "cannot expire a revoked caregiver relationship"
            )
        self.status = CaregiverRelationshipStatus.EXPIRED
        self.updated_at = expired_at or datetime.utcnow()