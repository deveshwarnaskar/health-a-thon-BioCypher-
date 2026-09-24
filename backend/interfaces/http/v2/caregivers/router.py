"""Caregiver v2 routes (Gate 10E-B).

THIN route layer. No business logic lives here.

    HTTP
     ↓
    authentication dependency (verified JWT → AuthenticatedContext)
     ↓
    authorization boundary (deny-by-default; caregiver-only discovery op)
     ↓
    application query (ListCaregiverPatientsHandler)
     ↓
    caregiver relationship repository (tenant-scoped + RLS)
     ↓
    patient resolution (tenant-scoped, active-only)
     ↓
    safe DTO → HTTP response

The caregiver identity is derived EXCLUSIVELY from ``ctx.actor_id``; neither
``caregiver_user_id`` nor ``tenant_id`` is ever accepted from the client.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries import ListCaregiverPatients
from backend.application.services import ListCaregiverPatientsHandler
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_clock,
    get_unit_of_work,
)
from backend.interfaces.http.ops.audit import audit_dependency
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.schemas import (
    CaregiverPatientListItemResponse,
    CaregiverPatientListResponse,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import authorize_or_403

caregivers_router = APIRouter()


@caregivers_router.get(
    "/me/patients",
    response_model=CaregiverPatientListResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="caregiver.patient_list",
                resource_id_from=None,
                atomic=False,
            )
        )
    ],
)
async def list_caregiver_patients(
    request: Request,
    response: Response,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    clock: Clock = Depends(get_clock),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CaregiverPatientListResponse:
    """List the patients this caregiver is currently authorized to access.

    Authorization is caregiver-role-explicit (deny-by-default for every other
    role). The result set is derived from the VERIFIED, non-expired,
    non-revoked relationships bound to the authenticated actor within the
    authenticated tenant, restricted to active patients at the query layer and
    at the authorization policy layer.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.LIST_CAREGIVER_PATIENTS)

    result = ListCaregiverPatientsHandler(uow, clock).handle(
        ListCaregiverPatients(caregiver_user_id=ctx.actor_id)
    )
    return CaregiverPatientListResponse(
        patient_count=result.patient_count,
        items=[
            CaregiverPatientListItemResponse(
                relationship_id=str(item.relationship_id),
                patient_id=str(item.patient_id),
                relationship_label=item.relationship_label,
                status=item.status,
                capabilities=list(item.capabilities),
                expires_at=item.expires_at,
                name=item.name,
            )
            for item in result.items
        ],
    )