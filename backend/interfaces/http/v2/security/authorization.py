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
    MANAGE_CAREGIVER_RELATIONSHIPS = "manage_caregiver_relationships"
    MANAGE_IDENTITY_MAPPINGS = "manage_identity_mappings"
    LIST_CAREGIVER_PATIENTS = "list_caregiver_patients"
    ADMIN = "admin"
    # Gate 10H-B mutation contracts. READ_WRITE separation is explicit:
    # WRITE_MEAL_OBSERVATIONS (draft), CONFIRM_MEAL_OBSERVATION (patient
    # confirmation/correction authority), WRITE_MEDICATION_ADMINISTRATION
    # (patient adherence event), READ/CREATE/COMPLETE_CARE_TASK (care-team
    # workflow), PROVISION_PATIENT + MANAGE_CARE_TEAM (administrator-only
    # provisioning).
    WRITE_MEAL_OBSERVATIONS = "write_meal_observations"
    CONFIRM_MEAL_OBSERVATION = "confirm_meal_observation"
    WRITE_MEDICATION_ADMINISTRATION = "write_medication_administration"
    READ_CARE_TASKS = "read_care_tasks"
    CREATE_CARE_TASK = "create_care_task"
    START_CARE_TASK = "start_care_task"
    COMPLETE_CARE_TASK = "complete_care_task"
    REASSIGN_CARE_TASK = "reassign_care_task"
    PROVISION_PATIENT = "provision_patient"
    MANAGE_CARE_TEAM = "manage_care_team"


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
        Operation.WRITE_MEAL_OBSERVATIONS,
        Operation.READ_CARE_TASKS,
        Operation.CREATE_CARE_TASK,
        Operation.START_CARE_TASK,
        Operation.COMPLETE_CARE_TASK,
        Operation.REASSIGN_CARE_TASK,
    }),
    "nurse": frozenset({
        Operation.READ_OBSERVATIONS,
        Operation.WRITE_OBSERVATIONS,
        Operation.READ_MEDICATION_PLANS,
        Operation.WRITE_MEDICATION_PLANS,
        Operation.READ_AI_ARTIFACTS,
        Operation.REVIEW_AI_ARTIFACT,
        Operation.READ_PATIENT,
        Operation.WRITE_MEAL_OBSERVATIONS,
        Operation.READ_CARE_TASKS,
        Operation.CREATE_CARE_TASK,
        Operation.START_CARE_TASK,
        Operation.COMPLETE_CARE_TASK,
        Operation.REASSIGN_CARE_TASK,
    }),
    "dietitian": frozenset({
        Operation.READ_OBSERVATIONS,
        Operation.WRITE_OBSERVATIONS,
        Operation.READ_MEDICATION_PLANS,
        Operation.WRITE_MEDICATION_PLANS,
        Operation.READ_AI_ARTIFACTS,
        Operation.REVIEW_AI_ARTIFACT,
        Operation.READ_PATIENT,
        Operation.WRITE_MEAL_OBSERVATIONS,
        Operation.READ_CARE_TASKS,
        Operation.CREATE_CARE_TASK,
        Operation.START_CARE_TASK,
        Operation.COMPLETE_CARE_TASK,
        Operation.REASSIGN_CARE_TASK,
    }),
    "care_coordinator": frozenset({
        Operation.READ_OBSERVATIONS,
        Operation.READ_MEDICATION_PLANS,
        Operation.READ_AI_ARTIFACTS,
        Operation.READ_PATIENT,
        Operation.WRITE_PATIENT,
        Operation.MANAGE_CAREGIVER_RELATIONSHIPS,
        Operation.READ_CARE_TASKS,
        Operation.CREATE_CARE_TASK,
        Operation.START_CARE_TASK,
        Operation.COMPLETE_CARE_TASK,
        Operation.REASSIGN_CARE_TASK,
    }),
    "field_health_worker": frozenset({
        Operation.READ_OBSERVATIONS,
        Operation.WRITE_OBSERVATIONS,
        Operation.READ_PATIENT,
        Operation.WRITE_MEAL_OBSERVATIONS,
        Operation.READ_CARE_TASKS,
        Operation.START_CARE_TASK,
        Operation.COMPLETE_CARE_TASK,
    }),
    "patient": frozenset({
        # Patient self-access: DENIED until Gate 08 identity mapping exists.
        # Empty set = deny all; self ops resolve exclusively via _is_self_allowed.
    }),
    "caregiver": frozenset({
        # Caregiver access: DENIED until Gate 08 relationship contracts exist.
        # Empty set = deny all; caregiver ops resolve via capabilities.
    }),
    "admin": frozenset({
        Operation.ADMIN,
        Operation.MANAGE_CAREGIVER_RELATIONSHIPS,
        Operation.MANAGE_IDENTITY_MAPPINGS,
        Operation.PROVISION_PATIENT,
        Operation.MANAGE_CARE_TEAM,
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


def is_proxy_role(ctx: AuthenticatedContext) -> bool:
    """True when the caller holds a patient/caregiver (proxy) identity role.

    Proxy roles NEVER hold coarse RBAC permissions. They are authorized only
    through the relationship/identity policy, never through the role matrix.
    """
    roles = set(ctx.roles)
    return bool(roles & {"patient", "caregiver"})


class RelationshipAuthorizationPolicy(DefaultAuthorizationPolicy):
    """Gate 08 authorization policy: coarse RBAC + relational identity.

    Non-proxy callers resolve through the standard deny-by-default role
    matrix. Proxy callers (patient/caregiver) are authorized exclusively via
    the relational identity contracts:
    - patient  → active identity→patient mapping bound to the target patient
    - caregiver → VERIFIED, non-expired relationship + capability grant
    """

    def __init__(self, clock=None, base: AuthorizationPolicy | None = None) -> None:
        from backend.infrastructure.config.clock import SystemClock

        self._clock = clock or SystemClock()
        self._base = base or DefaultAuthorizationPolicy()

    def is_allowed(
        self,
        ctx: AuthenticatedContext,
        operation: Operation,
        patient_id: UUID | None = None,
        uow=None,
    ) -> bool:
        if is_proxy_role(ctx):
            # Caregiver patient DISCOVERY (Gate 10E-B) is a self-scoped
            # operation: the caller is limited to relationships bound to
            # ctx.actor_id within ctx.tenant_id (enforced by the tenant-scoped
            # repository + application query + RLS). The caregiver role is the
            # explicit requirement; the returned set is relationally filtered,
            # so an empty result is a valid, authorized response.
            if operation is Operation.LIST_CAREGIVER_PATIENTS:
                return "caregiver" in ctx.roles
            return self._is_proxy_allowed(ctx, operation, patient_id, uow)
        return self._base.is_allowed(ctx, operation)

    def _is_proxy_allowed(
        self,
        ctx: AuthenticatedContext,
        operation: Operation,
        patient_id: UUID | None,
        uow,
    ) -> bool:
        if uow is None or patient_id is None:
            return False
        try:
            if "caregiver" in ctx.roles:
                return self._is_relationship_allowed(ctx, operation, patient_id, uow)
            return self._is_self_allowed(ctx, operation, patient_id, uow)
        except Exception:
            # Fail closed: any identity/relationship resolution error DENIES.
            return False

    def _is_relationship_allowed(
        self,
        ctx: AuthenticatedContext,
        operation: Operation,
        patient_id: UUID,
        uow,
    ) -> bool:
        from .capabilities import caregiver_required_capabilities

        required = caregiver_required_capabilities(operation)
        if not required:
            return False
        relationship = uow.caregiver_relationships.get_verified_for_patient(
            ctx.actor_id, patient_id
        )
        if relationship is None:
            return False
        if not relationship.is_granted_at(self._clock.now()):
            return False
        if not relationship.has_capabilities(required):
            return False
        # Gate 10E-B deactivated-patient invariant: a VERIFIED caregiver
        # relationship never authorizes access to a deactivated patient. This
        # is enforced HERE, at the shared authorization boundary, so caregiver
        # discovery and every patient-specific caregiver operation stay
        # consistent (mirrors the self-access invariant in _is_self_allowed).
        try:
            patient = uow.patients.get(patient_id)
        except Exception:
            return False
        return getattr(patient, "active", True)

    def _is_self_allowed(
        self,
        ctx: AuthenticatedContext,
        operation: Operation,
        patient_id: UUID,
        uow,
    ) -> bool:
        self_capable = {
            Operation.READ_OBSERVATIONS,
            Operation.WRITE_OBSERVATIONS,
            Operation.READ_PATIENT,
            Operation.WRITE_MEAL_OBSERVATIONS,
            Operation.CONFIRM_MEAL_OBSERVATION,
            Operation.WRITE_MEDICATION_ADMINISTRATION,
        }
        if operation not in self_capable:
            return False
        mapping = uow.identity_mappings.get_by_user_id(ctx.actor_id)
        if mapping is None or not mapping.active:
            return False
        if mapping.patient_id != patient_id:
            return False
        try:
            patient = uow.patients.get(patient_id)
        except Exception:
            return False
        return getattr(patient, "active", True)
