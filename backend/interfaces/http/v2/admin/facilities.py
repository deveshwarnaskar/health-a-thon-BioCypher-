"""Facilities administration routes (Gate 10K-B).

All routes are administrator-only (Operation.MANAGE_FACILITIES).
Tenant context is derived exclusively from the authenticated caller's JWT claims.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.application.commands.create_facility import CreateFacility
from backend.application.commands.deactivate_facility import DeactivateFacility
from backend.application.commands.update_facility import UpdateFacility
from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries.get_facility import GetFacility
from backend.application.queries.list_facilities import ListFacilities
from backend.application.services.create_facility import CreateFacilityHandler
from backend.application.services.deactivate_facility import DeactivateFacilityHandler
from backend.application.services.get_facility import GetFacilityHandler
from backend.application.services.list_facilities import ListFacilitiesHandler
from backend.application.services.update_facility import UpdateFacilityHandler
from backend.domain.exceptions import EntityNotFound
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_clock,
    get_event_publisher,
    get_id_generator,
    get_unit_of_work,
)
from backend.interfaces.http.ops.audit import audit_dependency, path_param
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.schemas import (
    CreateFacilityRequest,
    FacilityListResponse,
    FacilityResponse,
    UpdateFacilityRequest,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import authorize_or_403

admin_facilities_router = APIRouter()


def _correlation_id(request: Request) -> _uuid.UUID | None:
    raw = getattr(request.state, "correlation_id", None)
    if not raw:
        return None
    try:
        return _uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


@admin_facilities_router.get("/facilities", response_model=FacilityListResponse)
async def list_facilities(
    request: Request,
    response: Response,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limit: int = Query(50, ge=1, le=200),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> FacilityListResponse:
    """List facilities belonging to the caller's tenant."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.MANAGE_FACILITIES)

    result = ListFacilitiesHandler(uow).handle(ListFacilities(limit=limit))
    return FacilityListResponse(
        total=result.total,
        items=[
            FacilityResponse(
                facility_id=str(f.facility_id),
                name=f.name,
                active=f.active,
                created_at=f.created_at,
            )
            for f in result.items
        ],
    )


@admin_facilities_router.get(
    "/facilities/{facility_id}",
    response_model=FacilityResponse,
)
async def get_facility(
    request: Request,
    response: Response,
    facility_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> FacilityResponse:
    """Get single facility details."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.MANAGE_FACILITIES)

    try:
        facility_uuid = _uuid.UUID(facility_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid facility_id")

    try:
        f = GetFacilityHandler(uow).handle(GetFacility(facility_id=facility_uuid))
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Facility not found")

    return FacilityResponse(
        facility_id=str(f.facility_id),
        name=f.name,
        active=f.active,
        created_at=f.created_at,
    )


@admin_facilities_router.post(
    "/facilities",
    response_model=FacilityResponse,
    status_code=201,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="facility",
                resource_id_from=None,
                atomic=False,
            )
        )
    ],
)
async def create_facility(
    request: Request,
    response: Response,
    body: CreateFacilityRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> FacilityResponse:
    """Create a new facility under the caller's tenant."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.MANAGE_FACILITIES)

    result = CreateFacilityHandler(uow, events, clock, id_gen).handle(
        CreateFacility(
            name=body.name,
            correlation_id=_correlation_id(request),
        )
    )
    return FacilityResponse(
        facility_id=str(result.facility_id),
        name=result.name,
        active=result.active,
        created_at=result.created_at,
    )


@admin_facilities_router.patch(
    "/facilities/{facility_id}",
    response_model=FacilityResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.UPDATE,
                resource_type="facility",
                resource_id_from=lambda request: path_param(request, "facility_id"),
                atomic=False,
            )
        )
    ],
)
async def update_facility(
    request: Request,
    response: Response,
    facility_id: str,
    body: UpdateFacilityRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> FacilityResponse:
    """Update facility name or active status."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.MANAGE_FACILITIES)

    try:
        facility_uuid = _uuid.UUID(facility_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid facility_id")

    try:
        result = UpdateFacilityHandler(uow, events, clock, id_gen).handle(
            UpdateFacility(
                facility_id=facility_uuid,
                name=body.name,
                active=body.active,
                correlation_id=_correlation_id(request),
            )
        )
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Facility not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return FacilityResponse(
        facility_id=str(result.facility_id),
        name=result.name,
        active=result.active,
        created_at=result.created_at,
    )


@admin_facilities_router.post(
    "/facilities/{facility_id}/deactivate",
    response_model=FacilityResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.UPDATE,
                resource_type="facility",
                resource_id_from=lambda request: path_param(request, "facility_id"),
                atomic=False,
            )
        )
    ],
)
async def deactivate_facility(
    request: Request,
    response: Response,
    facility_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> FacilityResponse:
    """Deactivate a facility."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.MANAGE_FACILITIES)

    try:
        facility_uuid = _uuid.UUID(facility_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid facility_id")

    try:
        result = DeactivateFacilityHandler(uow, events, clock, id_gen).handle(
            DeactivateFacility(
                facility_id=facility_uuid,
                correlation_id=_correlation_id(request),
            )
        )
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Facility not found")

    return FacilityResponse(
        facility_id=str(result.facility_id),
        name=result.name,
        active=result.active,
        created_at=result.created_at,
    )


__all__ = ["admin_facilities_router"]
