"""Admin patient management routes (Gate 10K-B).

All routes are administrator-only (Operation.PROVISION_PATIENT or Operation.ADMIN).
Responses are strictly PHI-minimized operational DTOs:
no glucose observations, meals, medications, AI review artifacts, or clinical risk scores.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.application.commands import CreatePatient
from backend.application.commands.admin_deactivate_patient import AdminDeactivatePatient
from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries.admin_get_patient import AdminGetPatient
from backend.application.queries.admin_list_patients import AdminListPatients
from backend.application.services.admin_deactivate_patient import AdminDeactivatePatientHandler
from backend.application.services.admin_get_patient import AdminGetPatientHandler
from backend.application.services.admin_list_patients import AdminListPatientsHandler
from backend.application.services.create_patient import CreatePatientHandler
from backend.domain.exceptions import EntityNotFound
from backend.domain.value_objects import UHID, PhoneNumber
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
    AdminPatientListResponse,
    AdminPatientResponse,
    ProvisionPatientRequest,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import authorize_or_403

admin_patients_router = APIRouter()


def _correlation_id(request: Request) -> _uuid.UUID | None:
    raw = getattr(request.state, "correlation_id", None)
    if not raw:
        return None
    try:
        return _uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


@admin_patients_router.get(
    "/patients",
    response_model=AdminPatientListResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="admin.patient_cohort",
                resource_id_from=None,
                atomic=False,
            )
        )
    ],
)
async def admin_list_patients(
    request: Request,
    response: Response,
    facility_id: str | None = None,
    active: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> AdminPatientListResponse:
    """List operational patient records for the tenant (administrator-only, PHI-minimized)."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.PROVISION_PATIENT)

    facility_uuid = None
    if facility_id:
        try:
            facility_uuid = _uuid.UUID(facility_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid facility_id")

    result = AdminListPatientsHandler(uow).handle(
        AdminListPatients(
            facility_id=facility_uuid,
            active=active,
            limit=limit,
        )
    )
    return AdminPatientListResponse(
        total=result.total,
        items=[
            AdminPatientResponse(
                patient_id=str(p.patient_id),
                uh_id=p.uh_id,
                name=p.name,
                facility_id=str(p.facility_id) if p.facility_id else None,
                phone=p.phone,
                active=p.active,
                has_active_mapping=p.has_active_mapping,
                created_at=p.created_at,
            )
            for p in result.items
        ],
    )


@admin_patients_router.post(
    "/patients",
    response_model=AdminPatientResponse,
    status_code=201,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="patient.provision",
                resource_id_from=None,
                atomic=False,
            )
        )
    ],
)
async def admin_provision_patient(
    request: Request,
    response: Response,
    body: ProvisionPatientRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> AdminPatientResponse:
    """Provision a tenant patient record (administrator-only, PHI-minimized)."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.PROVISION_PATIENT)

    uh_id = UHID(body.uh_id) if body.uh_id else UHID("UNASSIGNED")
    phone = PhoneNumber(body.phone) if body.phone else None

    result = CreatePatientHandler(uow, events, clock, id_gen).handle(
        CreatePatient(
            name=body.name,
            facility_id=body.facility_id,
            uh_id=uh_id,
            phone=phone,
            correlation_id=_correlation_id(request),
        )
    )
    return AdminPatientResponse(
        patient_id=str(result.patient_id),
        uh_id=str(result.uh_id),
        name=result.name,
        facility_id=str(result.facility_id) if result.facility_id else None,
        phone=body.phone,
        active=result.active,
        has_active_mapping=False,
        created_at=result.created_at,
    )


@admin_patients_router.get(
    "/patients/{patient_id}",
    response_model=AdminPatientResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="admin.patient",
                resource_id_from=lambda request: path_param(request, "patient_id"),
                atomic=False,
            )
        )
    ],
)
async def admin_get_patient(
    request: Request,
    response: Response,
    patient_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> AdminPatientResponse:
    """Get single operational patient record (administrator-only, PHI-minimized)."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.PROVISION_PATIENT)

    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    try:
        p = AdminGetPatientHandler(uow).handle(AdminGetPatient(patient_id=patient_uuid))
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")

    return AdminPatientResponse(
        patient_id=str(p.patient_id),
        uh_id=p.uh_id,
        name=p.name,
        facility_id=str(p.facility_id) if p.facility_id else None,
        phone=p.phone,
        active=p.active,
        has_active_mapping=p.has_active_mapping,
        created_at=p.created_at,
    )


@admin_patients_router.post(
    "/patients/{patient_id}/deactivate",
    response_model=AdminPatientResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.UPDATE,
                resource_type="patient",
                resource_id_from=lambda request: path_param(request, "patient_id"),
                atomic=False,
            )
        )
    ],
)
async def admin_deactivate_patient(
    request: Request,
    response: Response,
    patient_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> AdminPatientResponse:
    """Deactivate a patient record (administrator-only)."""
    apply_rate_limit(request=request, response=response, tier=TIERS["admin"], limiter=limiter, ctx=ctx)
    authorize_or_403(ctx, policy, Operation.PROVISION_PATIENT)

    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    try:
        p = AdminDeactivatePatientHandler(uow, events, clock, id_gen).handle(
            AdminDeactivatePatient(
                patient_id=patient_uuid,
                correlation_id=_correlation_id(request),
            )
        )
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")

    return AdminPatientResponse(
        patient_id=str(p.patient_id),
        uh_id=p.uh_id,
        name=p.name,
        facility_id=str(p.facility_id) if p.facility_id else None,
        phone=p.phone,
        active=p.active,
        has_active_mapping=p.has_active_mapping,
        created_at=p.created_at,
    )


__all__ = ["admin_patients_router"]
