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

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

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


class LinkCaregiverPatientRequest(BaseModel):
    """Payload to link a caregiver account to a patient via UHID or identifier."""

    model_config = ConfigDict(extra="forbid")
    uhid: str = Field(..., min_length=2, max_length=64, description="Patient UHID or ID")
    relationship_label: str = Field(
        default="Primary Family Caregiver",
        min_length=1,
        max_length=100,
        description="Relationship to patient (e.g. Spouse, Parent, Child, Guardian)",
    )


@caregivers_router.post(
    "/link",
    response_model=CaregiverPatientListItemResponse,
    status_code=200,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="caregiver.patient_link",
                resource_id_from=None,
                atomic=False,
            )
        )
    ],
)
async def link_caregiver_patient(
    request: Request,
    response: Response,
    body: LinkCaregiverPatientRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    clock: Clock = Depends(get_clock),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CaregiverPatientListItemResponse:
    """Link authenticated caregiver account to a patient by UHID or patient ID.

    Grants verified family caregiver capabilities for observing and logging
    daily inputs (glucose, meals, care tasks).
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    if "caregiver" not in ctx.roles:
        raise HTTPException(status_code=403, detail="Caregiver role required")

    from backend.infrastructure.persistence.models.identity_models import CaregiverRelationshipModel
    from backend.infrastructure.persistence.models.patient_models import PatientModel
    from sqlalchemy import func, or_, select
    import uuid as _uuid

    clean_uhid = body.uhid.strip()
    session = getattr(uow, "session", None)
    if session is None:
        raise HTTPException(status_code=500, detail="Database session unavailable")

    # Normalize input by stripping common prefixes (e.g., PAIR-, UHID-, UH-)
    bare_code = clean_uhid
    for prefix in ("PAIR-", "pair-", "UHID-", "uhid-", "UH-", "uh-"):
        if bare_code.startswith(prefix):
            bare_code = bare_code[len(prefix):]
            break

    # 1. Match patient by UHID (case-insensitive) or UUID if valid
    parsed_uuid = None
    try:
        parsed_uuid = _uuid.UUID(clean_uhid)
    except ValueError:
        try:
            parsed_uuid = _uuid.UUID(bare_code)
        except ValueError:
            pass

    conditions = [
        func.lower(PatientModel.uh_id) == func.lower(clean_uhid),
        func.lower(PatientModel.uh_id) == func.lower(bare_code),
        func.lower(PatientModel.uh_id) == func.lower(f"UHID-{bare_code}"),
    ]
    if parsed_uuid:
        conditions.append(PatientModel.id == parsed_uuid)

    stmt = select(PatientModel).where(
        PatientModel.tenant_id == ctx.tenant_id,
        or_(*conditions),
    )
    patient = session.scalars(stmt).first()

    # 2. If not found by direct Patient UHID, check user mapping (pairing passcode or patient email)
    if patient is None:
        from backend.infrastructure.persistence.models.identity_models import IdentityPatientMappingModel
        from backend.infrastructure.persistence.models.user_models import UserModel
        from sqlalchemy import cast, String

        mapping_stmt = (
            select(PatientModel)
            .join(IdentityPatientMappingModel, IdentityPatientMappingModel.patient_id == PatientModel.id)
            .join(UserModel, UserModel.id == IdentityPatientMappingModel.user_id)
            .where(
                PatientModel.tenant_id == ctx.tenant_id,
                or_(
                    func.lower(UserModel.email) == func.lower(clean_uhid),
                    cast(UserModel.id, String).ilike(f"{bare_code.lower()}%"),
                ),
            )
        )
        patient = session.scalars(mapping_stmt).first()

    if patient is None or not getattr(patient, "active", True):
        raise HTTPException(
            status_code=404,
            detail=f"Patient with UHID '{clean_uhid}' was not found in your facility/tenant.",
        )

    full_capabilities = [
        "read_glucose",
        "create_glucose",
        "read_meal",
        "create_meal",
        "read_care_tasks",
        "complete_care_tasks",
        "read_medication_events",
        "create_medication_events",
    ]

    now_time = clock.now()

    # Check for existing relationship
    rel_stmt = select(CaregiverRelationshipModel).where(
        CaregiverRelationshipModel.tenant_id == ctx.tenant_id,
        CaregiverRelationshipModel.patient_id == patient.id,
        CaregiverRelationshipModel.caregiver_user_id == ctx.actor_id,
    )
    existing_rel = session.scalars(rel_stmt).first()

    if existing_rel is not None:
        existing_rel.status = "verified"
        existing_rel.relationship_label = body.relationship_label.strip() or "Primary Family Caregiver"
        existing_rel.capabilities = full_capabilities
        existing_rel.revoked_at = None
        existing_rel.verified_at = now_time
        existing_rel.updated_at = now_time
        rel = existing_rel
    else:
        rel = CaregiverRelationshipModel(
            id=_uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            patient_id=patient.id,
            caregiver_user_id=ctx.actor_id,
            relationship_label=body.relationship_label.strip() or "Primary Family Caregiver",
            status="verified",
            capabilities=full_capabilities,
            verified_at=now_time,
            created_at=now_time,
            updated_at=now_time,
        )
        session.add(rel)

    uow.commit()

    return CaregiverPatientListItemResponse(
        relationship_id=str(rel.id),
        patient_id=str(patient.id),
        relationship_label=rel.relationship_label,
        status="verified",
        capabilities=full_capabilities,
        expires_at=rel.expires_at,
        name=patient.name,
    )