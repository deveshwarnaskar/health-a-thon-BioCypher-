"""Relational-identity administration routes (Gate 08).

Identity→patient mappings are administrator-managed ONLY:

    POST  /api/v2/admin/identity-mappings/{...}         → bind identity to patient
    GET   /api/v2/admin/identity-mappings               → list mappings
    POST  /api/v2/admin/identity-mappings/{id}/deactivate → deny patient self-access

There is NO self-service mapping endpoint. The mapping is keyed on user_id, so
phone-number changes never alter identity. Only the ``admin`` role holds the
MANAGE_IDENTITY_MAPPINGS operation.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.application.commands import (
    CreateIdentityMapping,
    DeactivateIdentityMapping,
)
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.create_identity_mapping import CreateIdentityMappingHandler
from backend.application.services.deactivate_identity_mapping import DeactivateIdentityMappingHandler
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_clock,
    get_event_publisher,
    get_id_generator,
    get_unit_of_work,
)
from backend.interfaces.http.v2.schemas import (
    CreateIdentityMappingRequest,
    IdentityMappingResponse,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import authorize_or_403

admin_router = APIRouter()


def _correlation_id(request: Request) -> _uuid.UUID | None:
    raw = getattr(request.state, "correlation_id", None)
    if not raw:
        return None
    try:
        return _uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _to_response(mapping) -> IdentityMappingResponse:
    return IdentityMappingResponse(
        mapping_id=str(mapping.id),
        user_id=str(mapping.user_id),
        patient_id=str(mapping.patient_id),
        active=mapping.active,
        created_at=mapping.created_at,
    )


@admin_router.post("/identity-mappings", response_model=IdentityMappingResponse, status_code=201)
async def create_identity_mapping(
    request: Request,
    body: CreateIdentityMappingRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
) -> IdentityMappingResponse:
    """Bind a platform identity (user_id) to a tenant patient.

    Administrator-only. The mapping is the sole source of patient self-access.
    """
    authorize_or_403(ctx, policy, Operation.MANAGE_IDENTITY_MAPPINGS)

    result = CreateIdentityMappingHandler(uow, events, clock, id_gen).handle(
        CreateIdentityMapping(
            user_id=body.user_id,
            patient_id=body.patient_id,
            correlation_id=_correlation_id(request),
        )
    )
    mapping = uow.identity_mappings.get(result.mapping_id)
    return _to_response(mapping)


@admin_router.get("/identity-mappings", response_model=list[IdentityMappingResponse])
async def list_identity_mappings(
    request: Request,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> list[IdentityMappingResponse]:
    """List identity→patient mappings (administrator-only)."""
    authorize_or_403(ctx, policy, Operation.MANAGE_IDENTITY_MAPPINGS)
    mappings = uow.identity_mappings.list()
    return [_to_response(m) for m in mappings]


@admin_router.post("/identity-mappings/{mapping_id}/deactivate", response_model=IdentityMappingResponse)
async def deactivate_identity_mapping(
    request: Request,
    mapping_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
) -> IdentityMappingResponse:
    """Deactivate an identity mapping, revoking patient self-access."""
    authorize_or_403(ctx, policy, Operation.MANAGE_IDENTITY_MAPPINGS)

    try:
        mapping_uuid = _uuid.UUID(mapping_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mapping_id")

    result = DeactivateIdentityMappingHandler(uow, events, clock, id_gen).handle(
        DeactivateIdentityMapping(
            mapping_id=mapping_uuid,
            correlation_id=_correlation_id(request),
        )
    )
    mapping = uow.identity_mappings.get(result.mapping_id)
    return _to_response(mapping)