"""AuthenticatedContext and AuthorizationPolicy (Gate 07).

AuthenticatedContext is the application-owned contract representing the
cryptographically verified identity of the caller. It is constructed from
verified JWT claims, NOT from request body fields.

AuthorizationPolicy implements DENY-BY-DEFAULT RBAC. Every operation must
be explicitly permitted; unknown roles/operations are denied.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedContext:
    """Immutable, application-owned security context.

    Values originate from verified authentication only. Never from request JSON.
    """

    actor_id: UUID
    tenant_id: UUID
    roles: tuple[str, ...] = ()
    facility_id: UUID | None = None
    username: str = ""


class Operation(str, Enum):
    """Coarse-grained operations for authorization decisions."""

    READ_OBSERVATIONS = "read_observations"
    WRITE_OBSERVATIONS = "write_observations"
    READ_MEDICATION_PLANS = "read_medication_plans"
    WRITE_MEDICATION_PLANS = "write_medication_plans"
    READ_AI_ARTIFACTS = "read_ai_artifacts"
    GENERATE_AI_ARTIFACT = "generate_ai_artifact"
    REVIEW_AI_ARTIFACT = "review_ai_artifact"
    READ_PATIENT = "read_patient"
    WRITE_PATIENT = "write_patient"
    ADMIN = "admin"


# Role → permitted operations mapping (DENY-BY-DEFAULT: unlisted = denied)
_ROLE_PERMISSIONS: dict[str, FrozenSet[Operation]] = {
    "doctor": frozenset({
        Operation.READ_OBSERVATIONS,
        Operation.WRITE_OBSERVATIONS,
        Operation.READ_MEDICATION_PLANS,
        Operation.WRITE_MEDICATION_PLANS,
        Operation.READ_AI_ARTIFACTS,
        Operation.GENERATE_AI_ARTIFACT,
        Operation.REVIEW_AI_ARTIFACT,
        Operation.READ_PATIENT,
        Operation.WRITE_PATIENT,
    }),
    "nurse": frozenset({
        Operation.READ_OBSERVATIONS,
        Operation.WRITE_OBSERVATIONS,
        Operation.READ_MEDICATION_PLANS,
        Operation.WRITE_MEDICATION_PLANS,
        Operation.READ_AI_ARTIFACTS,
        Operation.REVIEW_AI_ARTIFACT,
        Operation.READ_PATIENT,
    }),
    "dietitian": frozenset({
        Operation.READ_OBSERVATIONS,
        Operation.WRITE_OBSERVATIONS,
        Operation.READ_MEDICATION_PLANS,
        Operation.WRITE_MEDICATION_PLANS,
        Operation.READ_AI_ARTIFACTS,
        Operation.REVIEW_AI_ARTIFACT,
        Operation.READ_PATIENT,
    }),
    "care_coordinator": frozenset({
        Operation.READ_OBSERVATIONS,
        Operation.READ_MEDICATION_PLANS,
        Operation.READ_AI_ARTIFACTS,
        Operation.READ_PATIENT,
        Operation.WRITE_PATIENT,
    }),
    "field_health_worker": frozenset({
        Operation.READ_OBSERVATIONS,
        Operation.WRITE_OBSERVATIONS,
        Operation.READ_PATIENT,
    }),
    "patient": frozenset({
        # Patient self-access: DENIED until Gate 08 identity mapping exists.
        # Empty set = deny all.
    }),
    "caregiver": frozenset({
        # Caregiver access: DENIED until Gate 08 relationship contracts exist.
        # Empty set = deny all.
    }),
    "admin": frozenset({
        Operation.ADMIN,
    }),
}


@runtime_checkable
class AuthorizationPolicy(Protocol):
    """Application-owned authorization contract."""

    def is_allowed(
        self,
        ctx: AuthenticatedContext,
        operation: Operation,
    ) -> bool: ...


class DefaultAuthorizationPolicy:
    """DENY-BY-DEFAULT RBAC policy.

    Only explicitly mapped role→operation pairs are allowed.
    Unknown roles, missing roles, empty roles → DENY.
    """

    def is_allowed(
        self,
        ctx: AuthenticatedContext,
        operation: Operation,
    ) -> bool:
        if not ctx.roles:
            return False
        for role in ctx.roles:
            permitted = _ROLE_PERMISSIONS.get(role, frozenset())
            if operation in permitted:
                return True
        return False
