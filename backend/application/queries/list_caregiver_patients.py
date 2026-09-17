"""ListCaregiverPatients query (Gate 10E-B).

Read-side input spell for caregiver patient discovery. The caregiver identity
is derived exclusively from the authenticated context (``ctx.actor_id``) by
the route — never from a client-supplied identifier.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListCaregiverPatients:
    caregiver_user_id: UUID