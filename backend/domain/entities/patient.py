"""Patient entity (Gate 03).

Identity + lifecycle + core invariants only. No database-specific fields and
no persistence code.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from ..exceptions import InvalidStateTransition
from ..value_objects import PhoneNumber, UHID


@dataclass
class Patient:
    id: UUID = field(default_factory=uuid4)
    uh_id: UHID = field(default_factory=lambda: UHID("UNASSIGNED"))
    name: str = ""
    phone: PhoneNumber | None = None
    facility_id: UUID | None = None
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def link_phone(self, phone: PhoneNumber) -> None:
        self.phone = phone

    def unlink_phone(self) -> None:
        self.phone = None

    def deactivate(self) -> None:
        if not self.active:
            raise InvalidStateTransition("patient is already inactive")
        self.active = False

    def reactivate(self) -> None:
        if self.active:
            raise InvalidStateTransition("patient is already active")
        self.active = True