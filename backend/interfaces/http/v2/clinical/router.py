"""Clinical v2 routes (Gate 07).

THIN route layer. No business logic lives here. Routes:

1. authenticate (verified JWT → AuthenticatedContext)
2. authorize (deny-by-default coarse RBAC)
3. resolve/scope the target patient (facility + tenant, RLS backstop)
4. build a command/query (from the authenticated context, never from raw bodies)
5. call the application use case
6. serialize the DTO result

Patient self-access and caregiver patient access remain DENIED (403) until
Gate 08 identity/relationship contracts exist.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.application.commands import CreateMedicationPlan, IngestGlucoseReading, ReviewAIArtifact
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries import GetPatientObservationFeed
from backend.application.services.create_medication_plan import CreateMedicationPlanHandler
from backend.application.services.get_patient_observation_feed import GetPatientObservationFeedHandler
from backend.application.services.ingest_glucose import IngestGlucoseHandler
from backend.application.services.review_ai_artifact import ReviewAIArtifactHandler
from backend.domain.exceptions import EntityNotFound
from backend.domain.value_objects import GlucoseValue, ReadingTag
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_clock,
    get_event_publisher,
    get_id_generator,
    get_unit_of_work,
)
from backend.interfaces.http.v2.schemas import (
    CreateMedicationPlanRequest,
    CreateMedicationPlanResponse,
    IngestGlucoseRequest,
    IngestGlucoseResponse,
    PatientObservationFeedResponse,
    ReviewAIArtifactRequest,
    ReviewAIArtifactResponse,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import (
    assert_tenant_scoped_patient,
    authorize_or_403,
    deny_unavailable_identity,
)

clinical_router = APIRouter()


def _correlation_id(request: Request) -> _uuid.UUID | None:
    raw = getattr(request.state, "correlation_id", None)
    if not raw:
        return None
    try:
        return _uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


@clinical_router.get("/observations", response_model=PatientObservationFeedResponse)
async def get_observations(
    request: Request,
    patient_id: str,
    limit: int = 50,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> PatientObservationFeedResponse:
    """Read the patient-facing observation feed for ONE scoped patient.

    Roles that cannot prove a relationship (patient, caregiver) are denied.
    Clinicians require a verified facility context matching the patient.
    """
    authorize_or_403(ctx, policy, Operation.READ_OBSERVATIONS)
    deny_unavailable_identity(ctx)

    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    try:
        patient = uow.patients.get(patient_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")

    assert_tenant_scoped_patient(ctx, patient)

    feed = GetPatientObservationFeedHandler(uow).handle(
        GetPatientObservationFeed(patient_id=patient_uuid, limit=min(limit, 200))
    )
    items: list[dict[str, Any]] = feed.to_dicts()
    return PatientObservationFeedResponse(patient_id=str(patient_uuid), items=items)


@clinical_router.post("/observations", response_model=IngestGlucoseResponse)
async def ingest_observations(
    request: Request,
    body: IngestGlucoseRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
) -> IngestGlucoseResponse:
    """Record a glucose observation for a scoped patient (clinician workflow).

    Patient/caregiver roles are denied (no self-access / relationship contract).
    """
    authorize_or_403(ctx, policy, Operation.WRITE_OBSERVATIONS)
    deny_unavailable_identity(ctx)

    try:
        patient = uow.patients.get(body.patient_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")

    assert_tenant_scoped_patient(ctx, patient)

    tag = ReadingTag(body.tag) if body.tag else None
    cmd = IngestGlucoseReading(
        patient_id=body.patient_id,
        value=GlucoseValue(body.value_mg_dl),
        taken_at=body.taken_at or clock.now(),
        tag=tag,
        correlation_id=_correlation_id(request),
    )
    result = IngestGlucoseHandler(uow, events, clock, id_gen).handle(cmd)
    return IngestGlucoseResponse(
        observation_id=str(result.observation_id),
        patient_id=str(result.patient_id),
        value_mg_dl=result.value_mg_dl,
        taken_at=result.taken_at,
    )


@clinical_router.post("/medication-plans", response_model=CreateMedicationPlanResponse)
async def create_medication_plan(
    request: Request,
    body: CreateMedicationPlanRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
) -> CreateMedicationPlanResponse:
    """Author a MedicationPlan. Clinician-authorized ONLY (domain invariant).

    The prescriber is the AUTHENTICATED actor (ctx.actor_id), never a raw body
    value. Patient, caregiver, AI, generic system process, and administrator
    are denied. The domain enforces ``CareTeamRole.can_author_medication``.
    """
    authorize_or_403(ctx, policy, Operation.WRITE_MEDICATION_PLANS)
    deny_unavailable_identity(ctx)

    try:
        patient = uow.patients.get(body.patient_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")

    assert_tenant_scoped_patient(ctx, patient)

    cmd = CreateMedicationPlan(
        patient_id=body.patient_id,
        prescribed_by_user_id=ctx.actor_id,
        medication=body.medication,
        instruction=body.instruction,
        correlation_id=_correlation_id(request),
    )
    result = CreateMedicationPlanHandler(uow, clock, id_gen).handle(cmd)
    return CreateMedicationPlanResponse(
        medication_plan_id=str(result.medication_plan_id),
        patient_id=str(result.patient_id),
    )


@clinical_router.post("/ai-artifacts/{artifact_id}/review", response_model=ReviewAIArtifactResponse)
async def review_ai_artifact(
    request: Request,
    artifact_id: str,
    body: ReviewAIArtifactRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
) -> ReviewAIArtifactResponse:
    """Licensed clinician review of a pending AI artifact.

    The reviewer is the AUTHENTICATED actor (ctx.actor_id), never a raw body
    value. Only doctor/nurse/dietitian roles hold REVIEW_AI_ARTIFACT. There is
    NO endpoint through which AI itself can approve or execute an artifact.
    """
    authorize_or_403(ctx, policy, Operation.REVIEW_AI_ARTIFACT)
    deny_unavailable_identity(ctx)

    try:
        artifact_uuid = _uuid.UUID(artifact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artifact_id")

    from backend.application.commands import ReviewDecision

    try:
        artifact = uow.ai_artifacts.get(artifact_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        patient = uow.patients.get(artifact.patient_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")
    assert_tenant_scoped_patient(ctx, patient)

    cmd = ReviewAIArtifact(
        artifact_id=artifact_uuid,
        reviewer_user_id=ctx.actor_id,
        decision=ReviewDecision(body.decision),
        edited_summary=body.edited_summary,
        correlation_id=_correlation_id(request),
    )
    result = ReviewAIArtifactHandler(uow, events, clock, id_gen).handle(cmd)
    return ReviewAIArtifactResponse(
        artifact_id=str(result.artifact_id),
        state=result.state,
        reviewed_by_user_id=str(result.reviewed_by_user_id),
    )