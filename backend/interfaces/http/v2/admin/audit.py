"""Audit-trail administration routes (Gate 09).

    GET /api/v2/admin/audit-events — list the tenant's immutable audit trail.

Administrator-only (``admin`` role). The store is tenant-scoped, so an admin
can only ever read their own tenant's history; PostgreSQL RLS reinforces this.
Responses are PHI-minimal by construction (see ``AuditEvent``).
"""

from __future__ import annotations

from datetime import datetime
import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from backend.application.ports.unit_of_work import UnitOfWork
from backend.infrastructure.persistence.ops.audit_store import SqlAlchemyAuditStore
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_unit_of_work,
)
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import authorize_or_403

admin_audit_router = APIRouter()


class AuditEventResponse(BaseModel):
    audit_event_id: str
    tenant_id: str
    actor_id: str
    actor_type: str
    action: str
    resource_type: str
    resource_id: str | None = None
    occurred_at: str
    correlation_id: str = ""
    source_ip: str | None = None
    outcome: str
    reason: str | None = None


@admin_audit_router.get("/audit-events", response_model=list[AuditEventResponse])
async def list_audit_events(
    request: Request,
    response: Response,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limit: int = Query(50, ge=1, le=200),
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> list[AuditEventResponse]:
    """List the authenticated tenant's audit trail (administrator-only)."""
    authorize_or_403(ctx, policy, Operation.MANAGE_IDENTITY_MAPPINGS)
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)

    actor_uuid = None
    if actor_id:
        try:
            actor_uuid = _uuid.UUID(actor_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid actor_id")

    events = SqlAlchemyAuditStore(uow.session, uow.tenant_id).query(
        limit=limit,
        actor_id=actor_uuid,
        action=action,
        resource_type=resource_type,
        start_time=start_time,
        end_time=end_time,
    )
    return [
        AuditEventResponse(
            audit_event_id=str(e.audit_event_id),
            tenant_id=str(e.tenant_id),
            actor_id=str(e.actor_id),
            actor_type=e.actor_type,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id or None,
            occurred_at=e.occurred_at.isoformat(),
            correlation_id=e.correlation_id,
            source_ip=e.source_ip,
            outcome=e.outcome,
            reason=e.reason,
        )
        for e in events
    ]


__all__ = ["admin_audit_router"]