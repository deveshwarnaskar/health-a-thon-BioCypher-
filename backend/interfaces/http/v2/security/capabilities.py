"""Caregiver capability allow-list (Gate 08).

Proxy roles NEVER hold coarse RBAC permissions. Caregiver access is governed by
an explicit, operation-specific capability allow-list tied to the VERIFIED
relationship. Anything not permitted here is DENIED.
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet

from .authorization import Operation


class CaregiverCapability(str, Enum):
    """The 8 allowed caregiver capability tokens (everything else is DENY)."""

    READ_GLUCOSE = "read_glucose"
    CREATE_GLUCOSE = "create_glucose"
    READ_MEAL = "read_meal"
    CREATE_MEAL = "create_meal"
    READ_MEDICATION_EVENTS = "read_medication_events"
    CREATE_MEDICATION_EVENTS = "create_medication_events"
    READ_CARE_TASKS = "read_care_tasks"
    COMPLETE_CARE_TASKS = "complete_care_tasks"


# Operation → capabilities required for a caregiver grant.
# ALL listed capabilities are required for the matching operation.
_CAREGIVER_OPERATION_REQUIREMENTS: dict[Operation, FrozenSet[CaregiverCapability]] = {
    # Reading the observation feed exposes blood-glucose values and meal
    # entries: both read capabilities must be granted.
    Operation.READ_OBSERVATIONS: frozenset({
        CaregiverCapability.READ_GLUCOSE,
        CaregiverCapability.READ_MEAL,
    }),
    Operation.WRITE_OBSERVATIONS: frozenset({
        CaregiverCapability.CREATE_GLUCOSE,
    }),
}


def caregiver_required_capabilities(operation: Operation) -> FrozenSet[CaregiverCapability]:
    """Return the capability set a caregiver must hold for ``operation``.

    Unlisted operations return an empty set → caregiver is always denied.
    """
    return _CAREGIVER_OPERATION_REQUIREMENTS.get(operation, frozenset())