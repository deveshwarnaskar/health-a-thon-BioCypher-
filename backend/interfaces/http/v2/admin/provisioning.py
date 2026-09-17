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

from fastapi import APIRouter, Depends, Request, Response

from backend.application.commands import AddCareTeamMember
from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.add_care_team_member import AddCareTeamMemberHandler
from backend.domain.entities import CareTeamRole
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_clock,
    get_event_publisher,
    get_id_generator,
    get_unit_of_work,
)
from backend.interfaces.http.ops.audit import audit_dependency
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.schemas import (
    CareTeamMemberResponse,
    ProvisionCareTeamMemberRequest,
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