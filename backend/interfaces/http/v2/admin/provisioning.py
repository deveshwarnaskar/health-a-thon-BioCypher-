"""Care-team provisioning routes (Gate 10H-B).

    POST /api/v2/admin/care-team-members → create a clinician membership

Administrator-only (``admin`` role holds MANAGE_CARE_TEAM). The tenant is the
authenticated JWT tenant — never a client field. This is the ONLY production
path that introduces clinician membership records; there is no self-service
clinician enrollment.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.application.commands import AddCareTeamMember
from backend.application.commands.deactivate_care_team_member import DeactivateCareTeamMember
from backend.application.commands.update_care_team_member import UpdateCareTeamMember
from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries.get_care_team_member import GetCareTeamMember
from backend.application.queries.list_care_team_members import ListCareTeamMembers
from backend.application.services.add_care_team_member import AddCareTeamMemberHandler
from backend.application.services.deactivate_care_team_member import DeactivateCareTeamMemberHandler
from backend.application.services.get_care_team_member import GetCareTeamMemberHandler
from backend.application.services.list_care_team_members import ListCareTeamMembersHandler
from backend.application.services.update_care_team_member import UpdateCareTeamMemberHandler
from backend.domain.entities import CareTeamRole
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
    CareTeamMemberListResponse,
    CareTeamMemberResponse,
    ProvisionCareTeamMemberRequest,
    UpdateCareTeamMemberRequest,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import authorize_or_403

admin_provisioning_router = APIRouter()


def _correlation_id(request: Request) -> _uuid.UUID | None:
    raw = getattr(request.state, "correlation_id", None)
    if not raw:
        return None
    try:
        return _uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


@admin_provisioning_router.post(
    "/care-team-members",
    response_model=CareTeamMemberResponse,
    status_code=201,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="care_team.member",
                resource_id_from=None,
                atomic=False,
            )
        )
    ],
)
async def provision_care_team_member(
    request: Request,
    response: Response,
    body: ProvisionCareTeamMemberRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CareTeamMemberResponse:
    """Provision a care-team membership (administrator-only).

    The role vocabulary is the frozen Phase 1 university set. Facility scoping
    is derived from the request's well-formed facility UUID; the authoritative
    tenant remains the JWT claim.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.MANAGE_CARE_TEAM)

    result = AddCareTeamMemberHandler(uow, events, clock, id_gen).handle(
        AddCareTeamMember(
            user_id=body.user_id,
            role=CareTeamRole(body.role),
            display_name=body.display_name,
            facility_id=body.facility_id,
            correlation_id=_correlation_id(request),
        )
    )
    return CareTeamMemberResponse(
        member_id=str(result.member_id),
        user_id=str(result.user_id),
        role=result.role,
        display_name=result.display_name,
        facility_id=str(result.facility_id) if result.facility_id else None,
        active=result.active,
    )


@admin_provisioning_router.get(
    "/care-team-members",
    response_model=CareTeamMemberListResponse,
)
async def list_care_team_members(
    request: Request,
    response: Response,
    facility_id: str | None = None,
    role: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CareTeamMemberListResponse:
    """List care-team members for the caller's tenant."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.MANAGE_CARE_TEAM)

    facility_uuid = None
    if facility_id:
        try:
            facility_uuid = _uuid.UUID(facility_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid facility_id")

    result = ListCareTeamMembersHandler(uow).handle(
        ListCareTeamMembers(
            facility_id=facility_uuid,
            role=role,
            limit=limit,
        )
    )
    return CareTeamMemberListResponse(
        total=result.total,
        items=[
            CareTeamMemberResponse(
                member_id=str(m.member_id),
                user_id=str(m.user_id),
                role=m.role,
                display_name=m.display_name,
                facility_id=str(m.facility_id) if m.facility_id else None,
                active=m.active,
            )
            for m in result.items
        ],
    )


@admin_provisioning_router.get(
    "/care-team-members/{member_id}",
    response_model=CareTeamMemberResponse,
)
async def get_care_team_member(
    request: Request,
    response: Response,
    member_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CareTeamMemberResponse:
    """Get single care-team member details."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.MANAGE_CARE_TEAM)

    try:
        member_uuid = _uuid.UUID(member_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid member_id")

    try:
        m = GetCareTeamMemberHandler(uow).handle(GetCareTeamMember(member_id=member_uuid))
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Care team member not found")

    return CareTeamMemberResponse(
        member_id=str(m.member_id),
        user_id=str(m.user_id),
        role=m.role,
        display_name=m.display_name,
        facility_id=str(m.facility_id) if m.facility_id else None,
        active=m.active,
    )


@admin_provisioning_router.patch(
    "/care-team-members/{member_id}",
    response_model=CareTeamMemberResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.UPDATE,
                resource_type="care_team.member",
                resource_id_from=lambda request: path_param(request, "member_id"),
                atomic=False,
            )
        )
    ],
)
async def update_care_team_member(
    request: Request,
    response: Response,
    member_id: str,
    body: UpdateCareTeamMemberRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CareTeamMemberResponse:
    """Update care-team member details (role, display_name, facility_id, active)."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.MANAGE_CARE_TEAM)

    try:
        member_uuid = _uuid.UUID(member_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid member_id")

    try:
        m = UpdateCareTeamMemberHandler(uow, events, clock, id_gen).handle(
            UpdateCareTeamMember(
                member_id=member_uuid,
                role=CareTeamRole(body.role) if body.role else None,
                display_name=body.display_name,
                facility_id=body.facility_id,
                active=body.active,
                correlation_id=_correlation_id(request),
            )
        )
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Care team member or facility not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return CareTeamMemberResponse(
        member_id=str(m.member_id),
        user_id=str(m.user_id),
        role=m.role,
        display_name=m.display_name,
        facility_id=str(m.facility_id) if m.facility_id else None,
        active=m.active,
    )


@admin_provisioning_router.post(
    "/care-team-members/{member_id}/deactivate",
    response_model=CareTeamMemberResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.REVOKE,
                resource_type="care_team.member",
                resource_id_from=lambda request: path_param(request, "member_id"),
                atomic=False,
            )
        )
    ],
)
async def deactivate_care_team_member(
    request: Request,
    response: Response,
    member_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CareTeamMemberResponse:
    """Deactivate care-team member."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.MANAGE_CARE_TEAM)

    try:
        member_uuid = _uuid.UUID(member_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid member_id")

    try:
        m = DeactivateCareTeamMemberHandler(uow, events, clock, id_gen).handle(
            DeactivateCareTeamMember(
                member_id=member_uuid,
                correlation_id=_correlation_id(request),
            )
        )
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Care team member not found")

    return CareTeamMemberResponse(
        member_id=str(m.member_id),
        user_id=str(m.user_id),
        role=m.role,
        display_name=m.display_name,
        facility_id=str(m.facility_id) if m.facility_id else None,
        active=m.active,
    )