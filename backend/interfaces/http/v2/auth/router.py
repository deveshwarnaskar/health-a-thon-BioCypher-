"""Auth v2 route (Gate 07).

POST /api/v2/auth/verify — verifies the supplied bearer credential through
the real authentication dependency. Returns minimum safe context.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.interfaces.http.dependencies import get_authenticated_context
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext

auth_router = APIRouter()


class AuthVerifyResponse(BaseModel):
    actor_id: str
    tenant_id: str
    roles: list[str]
    facility_id: str | None = None


@auth_router.get("/verify", response_model=AuthVerifyResponse)
async def verify_authentication(
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
) -> AuthVerifyResponse:
    """Verify the bearer token and return the authenticated context.

    Never returns raw JWT, signing secrets, or internal credentials.
    """
    return AuthVerifyResponse(
        actor_id=str(ctx.actor_id),
        tenant_id=str(ctx.tenant_id),
        roles=list(ctx.roles),
        facility_id=str(ctx.facility_id) if ctx.facility_id else None,
    )
