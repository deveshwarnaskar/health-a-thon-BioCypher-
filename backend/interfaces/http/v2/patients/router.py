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

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.application.commands import (
    RegisterCaregiverRelationship,
    RevokeCaregiverRelationship,
    VerifyCaregiverRelationship,
)
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
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
from backend.interfaces.http.v2.schemas import (
    CaregiverRelationshipListResponse,
    CaregiverRelationshipResponse,
    RegisterCaregiverRequest,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import authorize_patient_operation

patients_router = APIRouter()


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


@patients_router.post("/{patient_id}/caregivers", response_model=CaregiverRelationshipResponse, status_code=201)
async def register_caregiver(
    request: Request,
    patient_id: str,
    body: RegisterCaregiverRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
) -> CaregiverRelationshipResponse:
    """Register a caregiver relationship for a scoped patient (PENDING).

    Relationship registrations are facility-scoped: the registering
    coordinator must belong to the same facility as the patient. The granted
    capabilities are explicit; everything else is denied at policy time.
    """
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