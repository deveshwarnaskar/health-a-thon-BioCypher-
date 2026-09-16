"""Auth v2 route (Gate 07 + Gate 09).

GET /api/v2/auth/verify — verifies the supplied bearer credential through
the real authentication dependency. Returns minimum safe context. Records a
LOGIN audit event and applies the auth rate tier.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from backend.application.ops.contracts import AuditAction
from backend.interfaces.http.dependencies import get_authenticated_context
from backend.interfaces.http.ops.audit import audit_dependency
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext

auth_router = APIRouter()


class AuthVerifyResponse(BaseModel):
    actor_id: str
    tenant_id: str
    roles: list[str]
    facility_id: str | None = None


@auth_router.get(
    "/verify",
    response_model=AuthVerifyResponse,
    dependencies=[Depends(audit_dependency(action=AuditAction.LOGIN, resource_type="auth.verify", atomic=False))],
)
async def verify_authentication(
    request: Request,
    response: Response,
    logger_ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> AuthVerifyResponse:
    """Verify the bearer token and return the authenticated context.

    Never returns raw JWT, signing secrets, or internal credentials.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter, ctx=logger_ctx)
    return AuthVerifyResponse(
        actor_id=str(logger_ctx.actor_id),
        tenant_id=str(logger_ctx.tenant_id),
        roles=list(logger_ctx.roles),
        facility_id=str(logger_ctx.facility_id) if logger_ctx.facility_id else None,
    )
