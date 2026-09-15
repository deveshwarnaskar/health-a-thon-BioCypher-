"""Resource scoping and authorization helpers (Gate 07).

DENY-BY-DEFAULT resource resolution for patient-targeted operations:

- patient role → DENY (identity mapping is a Gate 08 contract)
- caregiver role → DENY (relationship contracts are a Gate 08 contract)
- clinician without facility context → DENY
- patient without facility context → DENY
- patient facility != authenticated facility → DENY

These rules ensure no universal doctor/caregiver bypass exists.
"""

from __future__ import annotations

import uuid as _uuid

from fastapi import HTTPException

from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)


def authorize_or_403(
    ctx: AuthenticatedContext,
    policy: AuthorizationPolicy,
    operation: Operation,
) -> None:
    """Deny-by-default coarse RBAC enforcement."""
    if not policy.is_allowed(ctx, operation):
        raise HTTPException(status_code=403, detail="Access denied")


def deny_unavailable_identity(ctx: AuthenticatedContext) -> None:
    """Deny patient/caregiver identity resolution until Gate 08 contracts exist."""
    if "patient" in ctx.roles:
        raise HTTPException(
            status_code=403,
            detail="Patient self-access is unavailable until identity mapping exists",
        )
    if "caregiver" in ctx.roles:
        raise HTTPException(
            status_code=403,
            detail="Caregiver relationship access is unavailable until relationship contracts exist",
        )


def assert_tenant_scoped_patient(
    ctx: AuthenticatedContext,
    patient: object,
) -> None:
    """Confirm the resolved patient belongs to the authenticated resource scope.

    ``patient`` is the tenant-scoped domain entity already resolved through the
    tenant-bound UnitOfWork (RLS backstop). Facility matching is enforced here
    so ``doctor``/``nurse`` roles never become universal patient access.
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