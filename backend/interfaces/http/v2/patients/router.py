"""Patient caregiver-relationship routes (Gate 08).

THIN route layer. Caregiver relationships are patient-scoped resources:
- registration (care_coordinator, facility-scoped) → PENDING
- verification (care_coordinator, facility-scoped) → VERIFIED
- listing (facility-scoped, scoped to one patient)
- revocation (facility-scoped) → REVOKED

Proxy roles (patient/caregiver) never manage relationships: the allowed
operation is facility-scoped and caregiver/patient roles hold no coarse
permission for it.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.application.commands import (
    CreatePatient,
    RegisterCaregiverRelationship,
    RevokeCaregiverRelationship,
    VerifyCaregiverRelationship,
)
from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries import GetPatient, ListPatients
from backend.application.services.create_patient import CreatePatientHandler
from backend.application.services.get_patient import GetPatientHandler
from backend.application.services.list_patients import ListPatientsHandler
from backend.application.services.register_caregiver import RegisterCaregiverHandler
from backend.application.services.revoke_caregiver import RevokeCaregiverHandler
from backend.application.services.verify_caregiver import VerifyCaregiverHandler
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
    CaregiverRelationshipListResponse,
    CaregiverRelationshipResponse,
    PatientListResponse,
    PatientSummaryResponse,
    ProvisionPatientRequest,
    ProvisionPatientResponse,
    RegisterCaregiverRequest,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import (
    assert_authorized_clinician_facility,
    assert_clinician_facility_context,
    authorize_or_403,
    authorize_patient_operation,
)
from backend.domain.exceptions import EntityNotFound
from backend.domain.value_objects import PhoneNumber, UHID

patients_router = APIRouter()

_audit_registered = audit_dependency(
    action=AuditAction.CREATE,
    resource_type="caregiver",
    resource_id_from=lambda request: request.path_params.get("patient_id"),
)


def _correlation_id(request: Request) -> _uuid.UUID | None:
    raw = getattr(request.state, "correlation_id", None)
    if not raw:
        return None
    try:
        return _uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _to_response(rel) -> CaregiverRelationshipResponse:
    return CaregiverRelationshipResponse(
        relationship_id=str(rel.id),
        patient_id=str(rel.patient_id),
        caregiver_user_id=str(rel.caregiver_user_id),
        relationship_label=rel.relationship,
        status=rel.status.value,
        capabilities=sorted(rel.capabilities),
        verified_at=rel.verified_at,
        revoked_at=rel.revoked_at,
        expires_at=rel.expires_at,
        created_at=rel.created_at,
    )


def _to_patient_response(record) -> PatientSummaryResponse:
    return PatientSummaryResponse(
        patient_id=str(record.patient_id),
        uh_id=record.uh_id,
        name=record.name,
        facility_id=str(record.facility_id) if record.facility_id else None,
        active=record.active,
        created_at=record.created_at,
    )


@patients_router.post(
    "",
    response_model=ProvisionPatientResponse,
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
async def provision_patient(
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
) -> ProvisionPatientResponse:
    """Provision a tenant patient record (administrator-only).

    The tenant is the authenticated JWT tenant — never a client field. The
    patient is created active and facility-scoped; no clinical authority, role,
    or observation surface is created here.
    """
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
    return ProvisionPatientResponse(
        patient_id=str(result.patient_id),
        uh_id=result.uh_id,
        name=result.name,
        facility_id=str(result.facility_id) if result.facility_id else None,
        active=result.active,
        created_at=result.created_at,
    )


@patients_router.get(
    "",
    response_model=PatientListResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="patient.cohort",
                resource_id_from=None,
                atomic=False,
            )
        )
    ],
)
async def list_patients(
    request: Request,
    response: Response,
    limit: int = 50,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> PatientListResponse:
    """Read the clinician's active patient cohort (facility-scoped).

    The cohort is restricted to the authenticated member's facility by the
    authoritative membership record — a client-supplied facility or UUID never
    widens scope. Proxy roles hold no coarse READ_PATIENT grant and are denied
    (a patient cannot enumerate other patients even in the same facility).
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.READ_PATIENT)
    facility_id = assert_clinician_facility_context(ctx, uow)

    result = ListPatientsHandler(uow).handle(
        ListPatients(facility_id=facility_id, limit=min(limit, 200))
    )
    return PatientListResponse(
        patient_count=result.patient_count,
        items=[_to_patient_response(p) for p in result.items],
    )


@patients_router.get(
    "/{patient_id}",
    response_model=PatientSummaryResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="patient",
                resource_id_from=lambda request: request.path_params.get("patient_id"),
                atomic=False,
            )
        )
    ],
)
async def get_patient(
    request: Request,
    response: Response,
    patient_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> PatientSummaryResponse:
    """Read ONE patient record by id (facility-scoped clinician read).

    Deny-by-default: proxy roles hold no coarse READ_PATIENT grant, so a
    patient/caregiver can never reach this endpoint. Cross-facility,
    cross-tenant, deactivated-patient, or missing patients never resolve.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.READ_PATIENT)

    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    try:
        patient = uow.patients.get(patient_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")
    assert_authorized_clinician_facility(ctx, uow, patient)
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Access denied")

    result = GetPatientHandler(uow).handle(
        GetPatient(patient_id=patient_uuid, facility_id=patient.facility_id)
    )
    return _to_patient_response(result)


@patients_router.post(
    "/{patient_id}/caregivers",
    response_model=CaregiverRelationshipResponse,
    status_code=201,
    dependencies=[Depends(_audit_registered)],
)
async def register_caregiver(
    request: Request,
    response: Response,
    patient_id: str,
    body: RegisterCaregiverRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CaregiverRelationshipResponse:
    """Register a caregiver relationship for a scoped patient (PENDING).

    Relationship registrations are facility-scoped: the registering
    coordinator must belong to the same facility as the patient. The granted
    capabilities are explicit; everything else is denied at policy time.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    authorize_patient_operation(
        ctx, policy, Operation.MANAGE_CAREGIVER_RELATIONSHIPS, patient_uuid, uow
    )

    cmd = RegisterCaregiverRelationship(
        patient_id=patient_uuid,
        caregiver_user_id=body.caregiver_user_id,
        relationship_label=body.relationship_label,
        capabilities=frozenset(body.capabilities or []),
        expires_at=body.expires_at,
        correlation_id=_correlation_id(request),
    )
    result = RegisterCaregiverHandler(uow, events, clock, id_gen).handle(cmd)
    relationship = uow.caregiver_relationships.get(result.relationship_id)
    return _to_response(relationship)


@patients_router.get("/{patient_id}/caregivers", response_model=CaregiverRelationshipListResponse)
async def list_caregivers(
    request: Request,
    patient_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> CaregiverRelationshipListResponse:
    """List caregiver relationships for ONE scoped patient."""
    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    authorize_patient_operation(
        ctx, policy, Operation.MANAGE_CAREGIVER_RELATIONSHIPS, patient_uuid, uow
    )

    rels = uow.caregiver_relationships.list_for_patient(patient_uuid)
    return CaregiverRelationshipListResponse(
        patient_id=str(patient_uuid),
        items=[_to_response(r) for r in rels],
    )


@patients_router.patch("/{patient_id}/caregivers/{relationship_id}/verify", response_model=CaregiverRelationshipResponse)
async def verify_caregiver(
    request: Request,
    patient_id: str,
    relationship_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
) -> CaregiverRelationshipResponse:
    """Verify a PENDING caregiver relationship (→ VERIFIED).

    Verification is a clinician-mediated, facility-scoped action; it is never
    self-served by the caregiver.
    """
    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")
    try:
        rel_uuid = _uuid.UUID(relationship_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid relationship_id")

    authorize_patient_operation(
        ctx, policy, Operation.MANAGE_CAREGIVER_RELATIONSHIPS, patient_uuid, uow
    )

    result = VerifyCaregiverHandler(uow, events, clock, id_gen).handle(
        VerifyCaregiverRelationship(
            relationship_id=rel_uuid,
            correlation_id=_correlation_id(request),
        )
    )
    relationship = uow.caregiver_relationships.get(result.relationship_id)
    return _to_response(relationship)


@patients_router.delete("/{patient_id}/caregivers/{relationship_id}", response_model=CaregiverRelationshipResponse)
async def revoke_caregiver(
    request: Request,
    patient_id: str,
    relationship_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
) -> CaregiverRelationshipResponse:
    """Revoke a caregiver relationship (→ REVOKED, immediately denies access)."""
    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")
    try:
        rel_uuid = _uuid.UUID(relationship_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid relationship_id")

    authorize_patient_operation(
        ctx, policy, Operation.MANAGE_CAREGIVER_RELATIONSHIPS, patient_uuid, uow
    )

    result = RevokeCaregiverHandler(uow, events, clock, id_gen).handle(
        RevokeCaregiverRelationship(
            relationship_id=rel_uuid,
            correlation_id=_correlation_id(request),
        )
    )
    relationship = uow.caregiver_relationships.get(result.relationship_id)
    return _to_response(relationship)