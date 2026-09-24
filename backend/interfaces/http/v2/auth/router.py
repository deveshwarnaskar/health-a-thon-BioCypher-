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
from backend.application.ports.clock import Clock
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.identity_patient_resolver import IdentityPatientResolver
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_clock,
    get_unit_of_work,
    get_unscoped_session,
)
from backend.interfaces.http.ops.audit import audit_dependency
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    _ROLE_PERMISSIONS,
)

auth_router = APIRouter()


class AuthVerifyResponse(BaseModel):
    actor_id: str
    tenant_id: str
    roles: list[str]
    facility_id: str | None = None


class PatientContextItem(BaseModel):
    patient_id: str
    relationship: str
    active: bool = True
    capabilities: list[str] = []


class AuthContextResponse(BaseModel):
    actor_id: str
    tenant_id: str
    roles: list[str]
    facility_id: str | None = None
    patient_id: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    onboarding_state: str = "ACTIVE"
    capabilities: list[str] = []
    available_patient_contexts: list[PatientContextItem] = []


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


@auth_router.get(
    "/context",
    response_model=AuthContextResponse,
    dependencies=[Depends(audit_dependency(action=AuditAction.LOGIN, resource_type="auth.context", atomic=False))],
)
async def get_auth_context(
    request: Request,
    response: Response,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    clock: Annotated[Clock, Depends(get_clock)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> AuthContextResponse:
    """Resolve authoritative authenticated bootstrap context (Gate 10P Section 23).

    Returns authenticated actor, tenant, roles, capabilities, available
    patient contexts, and onboarding state without exposing database models,
    PHI, or signing secrets.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter, ctx=ctx)

    patient_id: str | None = None
    onboarding_state = "ACTIVE"
    available_contexts: list[PatientContextItem] = []
    capabilities: list[str] = []

    if "patient" in ctx.roles:
        resolver = IdentityPatientResolver(uow)
        res = resolver.resolve(ctx.actor_id)
        if res.patient_id is not None:
            patient_id = str(res.patient_id)
            if res.active:
                onboarding_state = "ACTIVE"
                available_contexts.append(
                    PatientContextItem(
                        patient_id=str(res.patient_id),
                        relationship="self",
                        active=True,
                        capabilities=[
                            "read_observations",
                            "write_observations",
                            "read_patient",
                            "write_meal_observations",
                            "confirm_meal_observation",
                            "write_medication_administration",
                            "read_notifications",
                            "read_documents",
                        ],
                    )
                )
                capabilities = ["patient_self"]
            else:
                onboarding_state = "DEACTIVATED"
        else:
            onboarding_state = "IDENTITY_MAPPING_PENDING"

    elif "caregiver" in ctx.roles:
        rels = uow.caregiver_relationships.list_for_caregiver(ctx.actor_id)
        now = clock.now()
        for r in rels:
            if r.is_granted_at(now):
                try:
                    pat = uow.patients.get(r.patient_id)
                    if getattr(pat, "active", True):
                        available_contexts.append(
                            PatientContextItem(
                                patient_id=str(r.patient_id),
                                relationship=r.relationship,
                                active=True,
                                capabilities=sorted(list(r.capabilities)),
                            )
                        )
                except Exception:
                    continue
        if available_contexts:
            onboarding_state = "ACTIVE"
            patient_id = available_contexts[0].patient_id
            capabilities = available_contexts[0].capabilities
        else:
            onboarding_state = "RELATIONSHIP_PENDING"

    else:
        onboarding_state = "ACTIVE"
        for r in ctx.roles:
            ops = _ROLE_PERMISSIONS.get(r, frozenset())
            capabilities.extend([op.value for op in ops])
        capabilities = sorted(list(set(capabilities)))

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    db_session = getattr(uow, "session", None)
    if db_session is not None:
        from backend.infrastructure.persistence.models.user_models import UserModel
        from backend.infrastructure.persistence.models.patient_models import PatientModel
        from backend.infrastructure.persistence.models.clinician_models import CareTeamMemberModel
        from uuid import UUID

        try:
            actor_uuid = UUID(str(ctx.actor_id)) if not isinstance(ctx.actor_id, UUID) else ctx.actor_id
            user = db_session.query(UserModel).filter(UserModel.id == actor_uuid).first()
            if user:
                phone = user.phone
                email = user.email
            if "doctor" in ctx.roles or "clinician" in ctx.roles:
                doc = db_session.query(CareTeamMemberModel).filter(CareTeamMemberModel.user_id == actor_uuid).first()
                if doc and doc.display_name:
                    name = doc.display_name
            if not name and patient_id:
                pat_uuid = UUID(str(patient_id)) if not isinstance(patient_id, UUID) else patient_id
                pat = db_session.query(PatientModel).filter(PatientModel.id == pat_uuid).first()
                if pat:
                    if pat.name:
                        name = pat.name
                    if not phone and pat.phone:
                        phone = pat.phone
        except Exception:
            pass

    return AuthContextResponse(
        actor_id=str(ctx.actor_id),
        tenant_id=str(ctx.tenant_id),
        roles=list(ctx.roles),
        facility_id=str(ctx.facility_id) if ctx.facility_id else None,
        patient_id=patient_id,
        name=name,
        phone=phone,
        email=email,
        onboarding_state=onboarding_state,
        capabilities=capabilities,
        available_patient_contexts=available_contexts,
    )


# Mount custom auth routes (/login, /refresh, /logout, /register)
from .login import auth_custom_router

auth_router.include_router(auth_custom_router)

