"""Resource scoping and authorization helpers (Gate 07 → Gate 08).

DENY-BY-DEFAULT resource resolution for patient-targeted operations:

- patient role → authorized ONLY via an active identity→patient mapping
- caregiver role → authorized ONLY via a VERIFIED, non-expired relationship
- clinician without a CareTeamMember record → DENY
- clinician without a member facility context → DENY
- member/JWT facility conflict → DENY
- patient facility != authorized member facility → DENY

These rules ensure no universal doctor/caregiver bypass exists.
"""

from __future__ import annotations

import uuid as _uuid

from fastapi import HTTPException

from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
    is_proxy_role,
)


def authorize_or_403(
    ctx: AuthenticatedContext,
    policy: AuthorizationPolicy,
    operation: Operation,
) -> None:
    """Deny-by-default coarse RBAC enforcement."""
    if not policy.is_allowed(ctx, operation):
        raise HTTPException(status_code=403, detail="Access denied")


def authorize_patient_operation(
    ctx: AuthenticatedContext,
    policy: AuthorizationPolicy,
    operation: Operation,
    patient_id: _uuid.UUID,
    uow,
):
    """Resolve and authorize access to a scoped patient resource.

    Proxy roles (patient/caregiver) are authorized ONLY through the
    relational identity policy — never through the coarse role matrix. All
    other roles flow through coarse RBAC followed by membership/facility
    scoping. Returns the tenant-scoped patient entity on success.
    """
    if is_proxy_role(ctx):
        if not policy.is_allowed(ctx, operation, patient_id=patient_id, uow=uow):
            raise HTTPException(status_code=403, detail="Access denied")
        return _resolve_patient(uow, patient_id)

    authorize_or_403(ctx, policy, operation)
    patient = _resolve_patient(uow, patient_id)
    assert_authorized_clinician_facility(ctx, uow, patient)
    return patient


def _resolve_patient(uow, patient_id: _uuid.UUID):
    from backend.domain.exceptions import EntityNotFound

    try:
        return uow.patients.get(patient_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")


def assert_authorized_clinician_facility(
    ctx: AuthenticatedContext,
    uow,
    patient,
) -> None:
    """Enforce CareTeamMember-membership-based clinical authorization.

    The authenticated member record is authoritative for facility scoping.
    A missing member, inactive member, member without a facility, a JWT
    facility conflicting with the member's facility, or a patient outside
    the member's facility all DENY access.
    """
    from backend.domain.exceptions import EntityNotFound

    try:
        member = uow.care_team_members.get(ctx.actor_id)
    except EntityNotFound:
        raise HTTPException(
            status_code=403,
            detail="No active care team membership for this tenant",
        )

    if getattr(member, "active", True) is False:
        raise HTTPException(
            status_code=403,
            detail="Care team membership is inactive",
        )

    member_facility = getattr(member, "facility_id", None)
    if member_facility is None:
        raise HTTPException(
            status_code=403,
            detail="Clinician facility context is required for patient access",
        )

    if ctx.facility_id is not None and ctx.facility_id != member_facility:
        raise HTTPException(
            status_code=403,
            detail="Token facility conflicts with care team membership",
        )

    patient_facility = getattr(patient, "facility_id", None)
    if isinstance(patient_facility, str):
        try:
            patient_facility = _uuid.UUID(patient_facility)
        except ValueError:
            patient_facility = None
    if patient_facility is None or patient_facility != member_facility:
        raise HTTPException(
            status_code=403,
            detail="Access to this patient is outside your authorized facility",
        )


def assert_clinician_facility_context(ctx, uow) -> uuid.UUID:
    """Resolve and enforce the authenticated clinician's facility context.

    Returns the authoritative member facility UUID used to scope clinician
    READ LISTS (AI artifact queue, medication plans, patient cohort). The
    member record is authoritative: a missing member, inactive member, member
    without a facility, or a JWT facility conflicting with the member all DENY.
    """
    from backend.domain.exceptions import EntityNotFound

    try:
        member = uow.care_team_members.get(ctx.actor_id)
    except EntityNotFound:
        raise HTTPException(
            status_code=403,
            detail="No active care team membership for this tenant",
        )

    if getattr(member, "active", True) is False:
        raise HTTPException(
            status_code=403,
            detail="Care team membership is inactive",
        )

    member_facility = getattr(member, "facility_id", None)
    if member_facility is None:
        raise HTTPException(
            status_code=403,
            detail="Clinician facility context is required for patient access",
        )

    if ctx.facility_id is not None and ctx.facility_id != member_facility:
        raise HTTPException(
            status_code=403,
            detail="Token facility conflicts with care team membership",
        )

    return member_facility


def assert_tenant_scoped_patient(
    ctx: AuthenticatedContext,
    patient: object,
) -> None:
    """[Backward-compatible] Unsafe legacy wrapper.

    Do NOT use in new routes: the clinician path is handled by
    ``assert_authorized_clinician_facility``. This is retained for routes that
    do not carry a CareTeamMember relationship (e.g. legacy AI review), where
    the JWT facility claim is the only facility evidence available.
    """
    facility_id = getattr(patient, "facility_id", None)

    if ctx.facility_id is None:
        raise HTTPException(
            status_code=403,
            detail="Clinician facility context is required for patient access",
        )
    if facility_id is None:
        raise HTTPException(
            status_code=403,
            detail="Patient facility context is required for access",
        )
    if isinstance(facility_id, str):
        try:
            facility_id = _uuid.UUID(facility_id)
        except ValueError:
            facility_id = None
    if facility_id != ctx.facility_id:
        raise HTTPException(
            status_code=403,
            detail="Access to this patient is outside your authorized facility",
        )