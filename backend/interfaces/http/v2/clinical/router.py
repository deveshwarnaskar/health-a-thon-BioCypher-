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

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.application.commands import (
    ConfirmMealObservation,
    CreateMedicationPlan,
    IngestGlucoseReading,
    LogMealDraft,
    RecordMedicationAdministration,
    ReviewAIArtifact,
)
from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.queries import (
    GetAIReviewArtifact,
    GetClinicalObservationFeed,
    GetMedicationPlan,
    GetPatientObservationFeed,
    ListAIReviewArtifacts,
    ListMedicationPlans,
)
from backend.application.services.confirm_meal_observation import ConfirmMealObservationHandler
from backend.application.services.create_medication_plan import CreateMedicationPlanHandler
from backend.application.services.get_ai_review_artifact import GetAIReviewArtifactHandler
from backend.application.services.get_clinical_observation_feed import GetClinicalObservationFeedHandler
from backend.application.services.get_medication_plan import GetMedicationPlanHandler
from backend.application.services.get_patient_observation_feed import GetPatientObservationFeedHandler
from backend.application.services.ingest_glucose import IngestGlucoseHandler
from backend.application.services.list_ai_review_artifacts import ListAIReviewArtifactsHandler
from backend.application.services.list_medication_plans import ListMedicationPlansHandler
from backend.application.services.log_meal_draft import LogMealDraftHandler
from backend.application.services.record_medication_administration import (
    RecordMedicationAdministrationHandler,
)
from backend.application.services.review_ai_artifact import ReviewAIArtifactHandler
from backend.application.dtos.clinical import ClinicalGlucoseRecord, ClinicalMealRecord
from backend.domain.exceptions import EntityNotFound
from backend.domain.value_objects import GlucoseValue, KatoriVolume, MealPortion, ReadingTag
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_clock,
    get_event_publisher,
    get_id_generator,
    get_unit_of_work,
)
from backend.interfaces.http.ops.audit import audit_dependency, json_field, path_param
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.schemas import (
    AIArtifactListResponse,
    AIArtifactResponse,
    ClinicalObservationFeedResponse,
    ConfirmMealRequest,
    ConfirmMealResponse,
    CreateMedicationPlanRequest,
    CreateMedicationPlanResponse,
    IngestGlucoseRequest,
    IngestGlucoseResponse,
    LogMealRequest,
    LogMealResponse,
    MedicationPlanListResponse,
    MedicationPlanResponse,
    PatientObservationFeedResponse,
    RecordMedicationAdministrationRequest,
    RecordMedicationAdministrationResponse,
    ReviewAIArtifactRequest,
    ReviewAIArtifactResponse,
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

clinical_router = APIRouter()


def _correlation_id(request: Request) -> _uuid.UUID | None:
    raw = getattr(request.state, "correlation_id", None)
    if not raw:
        return None
    try:
        return _uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


async def _patient_query_param(request: Request) -> str | None:
    return request.query_params.get("patient_id")


@clinical_router.get(
    "/observations",
    response_model=PatientObservationFeedResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="patient.observation_feed",
                resource_id_from=_patient_query_param,
                atomic=False,
            )
        )
    ],
)
async def get_observations(
    request: Request,
    response: Response,
    patient_id: str,
    limit: int = 50,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> PatientObservationFeedResponse:
    """Read the patient-facing observation feed for ONE scoped patient.

    Proxy roles (patient/caregiver) are authorized through the relational
    identity policy. Clinicians require an active CareTeamMember record whose
    facility matches the patient's facility.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    authorize_patient_operation(
        ctx, policy, Operation.READ_OBSERVATIONS, patient_uuid, uow
    )

    feed = GetPatientObservationFeedHandler(uow).handle(
        GetPatientObservationFeed(patient_id=patient_uuid, limit=min(limit, 200))
    )
    items: list[dict[str, Any]] = feed.to_dicts()
    return PatientObservationFeedResponse(patient_id=str(patient_uuid), items=items)


@clinical_router.post(
    "/observations",
    response_model=IngestGlucoseResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="patient.observation",
                resource_id_from=lambda request: json_field(request, "patient_id"),
            )
        )
    ],
)
async def ingest_observations(
    request: Request,
    response: Response,
    body: IngestGlucoseRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> IngestGlucoseResponse:
    """Record a glucose observation for a scoped patient.

    Proxy roles (patient/caregiver) are authorized through the relational
    identity policy; proxy access to write requires the corresponding grant.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    authorize_patient_operation(
        ctx, policy, Operation.WRITE_OBSERVATIONS, body.patient_id, uow
    )

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


@clinical_router.post(
    "/medication-plans",
    response_model=CreateMedicationPlanResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="patient.medication_plan",
                resource_id_from=lambda request: json_field(request, "patient_id"),
            )
        )
    ],
)
async def create_medication_plan(
    request: Request,
    response: Response,
    body: CreateMedicationPlanRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CreateMedicationPlanResponse:
    """Author a MedicationPlan. Clinician-authorized ONLY (domain invariant).

    The prescriber is the AUTHENTICATED actor (ctx.actor_id), never a raw body
    value. Patient, caregiver, AI, generic system process, and administrator
    are denied. The domain enforces ``CareTeamRole.can_author_medication``.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    authorize_patient_operation(
        ctx, policy, Operation.WRITE_MEDICATION_PLANS, body.patient_id, uow
    )

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


@clinical_router.post(
    "/ai-artifacts/{artifact_id}/review",
    response_model=ReviewAIArtifactResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.REVIEW,
                resource_type="ai_artifact.review",
                resource_id_from=lambda request: path_param(request, "artifact_id"),
            )
        )
    ],
)
async def review_ai_artifact(
    request: Request,
    response: Response,
    artifact_id: str,
    body: ReviewAIArtifactRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> ReviewAIArtifactResponse:
    """Licensed clinician review of a pending AI artifact.

    The reviewer is the AUTHENTICATED actor (ctx.actor_id), never a raw body
    value. Only doctor/nurse/dietitian roles hold REVIEW_AI_ARTIFACT. There is
    NO endpoint through which AI itself can approve or execute an artifact.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["ai"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.REVIEW_AI_ARTIFACT)

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
    assert_authorized_clinician_facility(ctx, uow, patient)

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


@clinical_router.get(
    "/clinical-observations",
    response_model=ClinicalObservationFeedResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="patient.clinical_observation_feed",
                resource_id_from=_patient_query_param,
                atomic=False,
            )
        )
    ],
)
async def get_clinical_observation_feed(
    request: Request,
    response: Response,
    patient_id: str,
    limit: int = 50,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> ClinicalObservationFeedResponse:
    """Read the CLINICIAN observation feed for ONE scoped patient.

    Returns clinician-only analytical fields (carbohydrate grams, glycemic
    index). Deny-by-default: only roles holding coarse READ_OBSERVATIONS plus
    an active, facility-matching care team membership are allowed. Proxy roles
    (patient/caregiver) are 403 even with full caregiver read grants or a
    self identity mapping — the information boundary never collapses.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.READ_OBSERVATIONS)

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
        # Deactivated-patient invariant: deactivated patients never surface
        # through clinician reads.
        raise HTTPException(status_code=403, detail="Access denied")

    feed = GetClinicalObservationFeedHandler(uow).handle(
        GetClinicalObservationFeed(
            patient_id=patient_uuid,
            clinician_user_id=ctx.actor_id,
            limit=min(limit, 200),
        )
    )
    items: list[dict[str, Any]] = []
    for item in feed.items:
        if isinstance(item, ClinicalMealRecord):
            items.append(
                {
                    "kind": "meal",
                    "observation_id": str(item.observation_id),
                    "description": item.description,
                    "portion_label": item.portion_label,
                    "quantity": item.quantity,
                    "carbs_grams": item.carbs_grams,
                    "glycemic_index": item.glycemic_index,
                    "recorded_at": item.recorded_at,
                    "confirmation": item.confirmation,
                }
            )
        elif isinstance(item, ClinicalGlucoseRecord):
            items.append(
                {
                    "kind": "glucose",
                    "observation_id": str(item.observation_id),
                    "value_mg_dl": item.value_mg_dl,
                    "tag": item.tag,
                    "taken_at": item.taken_at,
                    "confirmation": item.confirmation,
                }
            )
    return ClinicalObservationFeedResponse(patient_id=str(patient_uuid), items=items)


@clinical_router.get(
    "/ai-artifacts",
    response_model=AIArtifactListResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="ai_artifact.queue",
                resource_id_from=None,
                atomic=False,
            )
        )
    ],
)
async def list_ai_artifacts(
    request: Request,
    response: Response,
    limit: int = 50,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> AIArtifactListResponse:
    """Read the clinician pending-review queue (facility-scoped).

    The queue only surfaces PENDING_REVIEW artifacts for active patients of the
    authenticated member's facility, deterministically ordered by creation time.
    Patient/caregiver roles hold no coarse READ_AI_ARTIFACTS and are denied.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.READ_AI_ARTIFACTS)
    facility_id = assert_clinician_facility_context(ctx, uow)

    result = ListAIReviewArtifactsHandler(uow).handle(
        ListAIReviewArtifacts(facility_id=facility_id, limit=min(limit, 200))
    )
    return AIArtifactListResponse(
        artifact_count=result.artifact_count,
        items=[
            AIArtifactResponse(
                artifact_id=str(item.artifact_id),
                patient_id=str(item.patient_id),
                artifact_kind=item.artifact_kind,
                state=item.state,
                summary=item.summary,
                created_at=item.created_at,
            )
            for item in result.items
        ],
    )


@clinical_router.get(
    "/ai-artifacts/{artifact_id}",
    response_model=AIArtifactResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="ai_artifact",
                resource_id_from=lambda request: path_param(request, "artifact_id"),
                atomic=False,
            )
        )
    ],
)
async def get_ai_artifact(
    request: Request,
    response: Response,
    artifact_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> AIArtifactResponse:
    """Read ONE AI review artifact by id.

    Cross-facility, cross-tenant, deactivated-patient, or missing artifacts
    never resolve. Proxy roles hold no coarse read grant and are denied.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.READ_AI_ARTIFACTS)

    try:
        artifact_uuid = _uuid.UUID(artifact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artifact_id")

    try:
        artifact = uow.ai_artifacts.get(artifact_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        patient = uow.patients.get(artifact.patient_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")
    assert_authorized_clinician_facility(ctx, uow, patient)
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Access denied")

    result = GetAIReviewArtifactHandler(uow).handle(
        GetAIReviewArtifact(artifact_id=artifact_uuid, facility_id=patient.facility_id)
    )
    return AIArtifactResponse(
        artifact_id=str(result.artifact_id),
        patient_id=str(result.patient_id),
        artifact_kind=result.artifact_kind,
        state=result.state,
        summary=result.summary,
        created_at=result.created_at,
    )


@clinical_router.get(
    "/medication-plans",
    response_model=MedicationPlanListResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="patient.medication_plan_list",
                resource_id_from=None,
                atomic=False,
            )
        )
    ],
)
async def list_medication_plans(
    request: Request,
    response: Response,
    limit: int = 50,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> MedicationPlanListResponse:
    """Read clinician-authored medication plans for the member's facility.

    Plans are clinician-authored-only aggregates; proxy roles and AI never
    hold coarse READ_MEDICATION_PLANS and are denied. Medical instructions are
    exposed ONLY through this clinician-scoped read.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.READ_MEDICATION_PLANS)
    facility_id = assert_clinician_facility_context(ctx, uow)

    result = ListMedicationPlansHandler(uow).handle(
        ListMedicationPlans(facility_id=facility_id, limit=min(limit, 200))
    )
    return MedicationPlanListResponse(
        plan_count=result.plan_count,
        items=[
            MedicationPlanResponse(
                medication_plan_id=str(item.medication_plan_id),
                patient_id=str(item.patient_id),
                medication=item.medication,
                instruction=item.instruction,
                active=item.active,
                prescribed_by_role=item.prescribed_by_role,
                created_at=item.created_at,
            )
            for item in result.items
        ],
    )


@clinical_router.get(
    "/medication-plans/{plan_id}",
    response_model=MedicationPlanResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="patient.medication_plan",
                resource_id_from=lambda request: path_param(request, "plan_id"),
                atomic=False,
            )
        )
    ],
)
async def get_medication_plan(
    request: Request,
    response: Response,
    plan_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> MedicationPlanResponse:
    """Read ONE clinician-authored medication plan by id.

    Cross-facility, cross-tenant, deactivated-patient, or missing plans never
    resolve. Proxy roles are denied at the coarse boundary.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.READ_MEDICATION_PLANS)

    try:
        plan_uuid = _uuid.UUID(plan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid plan_id")

    try:
        plan = uow.medication_plans.get(plan_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Medication plan not found")

    try:
        patient = uow.patients.get(plan.patient_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")
    assert_authorized_clinician_facility(ctx, uow, patient)
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Access denied")

    result = GetMedicationPlanHandler(uow).handle(
        GetMedicationPlan(plan_id=plan_uuid, facility_id=patient.facility_id)
    )
    return MedicationPlanResponse(
        medication_plan_id=str(result.medication_plan_id),
        patient_id=str(result.patient_id),
        medication=result.medication,
        instruction=result.instruction,
        active=result.active,
        prescribed_by_role=result.prescribed_by_role,
        created_at=result.created_at,
    )


def _meal_portion(body_portion) -> MealPortion | None:
    """Build the canonical MealPortion VO from a validated request schema."""
    if body_portion is None:
        return None
    return MealPortion(
        food_key=body_portion.food_key,
        katori=KatoriVolume(body_portion.katori_volume_ml),
        quantity=body_portion.quantity,
    )


@clinical_router.post(
    "/meals",
    response_model=LogMealResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="patient.meal",
                resource_id_from=lambda request: json_field(request, "patient_id"),
            )
        )
    ],
)
async def log_meal_draft(
    request: Request,
    response: Response,
    body: LogMealRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> LogMealResponse:
    """Draft a meal observation for a scoped patient (unconfirmed).

    Patient self-access and caregiver CREATE_MEAL grants flow through the
    relational policy; clinicians require an active facility-matching
    membership. The patient-facing DTO carries description/portion only —
    analytic interpretation (carbs/GI) is never produced here.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    patient = authorize_patient_operation(
        ctx, policy, Operation.WRITE_MEAL_OBSERVATIONS, body.patient_id, uow
    )
    if not getattr(patient, "active", True):
        # Deactivated-patient invariant: proxies are already denied at the
        # policy boundary; the clinician path enforces it here too.
        raise HTTPException(status_code=403, detail="Access denied")

    cmd = LogMealDraft(
        patient_id=body.patient_id,
        description=body.description,
        recorded_at=body.recorded_at or clock.now(),
        portion=_meal_portion(body.portion),
        correlation_id=_correlation_id(request),
    )
    result = LogMealDraftHandler(uow, events, clock, id_gen).handle(cmd)
    observation = uow.meal_observations.get(result.meal_observation_id)
    return LogMealResponse(
        meal_observation_id=str(result.meal_observation_id),
        patient_id=str(result.patient_id),
        portion_label=observation.portion.katori.label if observation.portion else None,
        quantity=observation.portion.quantity if observation.portion else None,
    )


@clinical_router.post(
    "/meals/{meal_observation_id}/confirm",
    response_model=ConfirmMealResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.UPDATE,
                resource_type="patient.meal",
                resource_id_from=lambda request: path_param(request, "meal_observation_id"),
            )
        )
    ],
)
async def confirm_meal_observation(
    request: Request,
    response: Response,
    meal_observation_id: str,
    body: ConfirmMealRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> ConfirmMealResponse:
    """Patient confirmation/correction of a pending meal observation.

    Confirmation authority is PATIENT-ONLY (Domain Gate 03): the confirmed_by
    phone is resolved from the authoritative patient record, never from the
    request body. A patient without a bound phone cannot confirm (409).
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    try:
        meal_uuid = _uuid.UUID(meal_observation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meal_observation_id")

    try:
        observation = uow.meal_observations.get(meal_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Meal observation not found")

    patient = authorize_patient_operation(
        ctx, policy, Operation.CONFIRM_MEAL_OBSERVATION, observation.patient_id, uow
    )
    if patient.phone is None:
        raise HTTPException(
            status_code=409,
            detail="Patient phone is required to confirm a meal observation",
        )

    cmd = ConfirmMealObservation(
        meal_observation_id=meal_uuid,
        confirmed_by=patient.phone,
        corrected_description=body.corrected_description,
        corrected_portion=_meal_portion(body.corrected_portion),
        correlation_id=_correlation_id(request),
    )
    result = ConfirmMealObservationHandler(uow, events, clock, id_gen).handle(cmd)
    return ConfirmMealResponse(
        meal_observation_id=str(result.meal_observation_id),
        patient_id=str(observation.patient_id),
        confirmation=result.confirmation,
    )


@clinical_router.post(
    "/medication-administrations",
    response_model=RecordMedicationAdministrationResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="patient.medication_administration",
                resource_id_from=lambda request: json_field(request, "medication_plan_id"),
            )
        )
    ],
)
async def record_medication_administration(
    request: Request,
    response: Response,
    body: RecordMedicationAdministrationRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> RecordMedicationAdministrationResponse:
    """Record a PATIENT adherence event against an active clinician-authored plan.

    Medication authority stays clinician-only: the plan is loaded read-only and
    never created or modified here. Self-access is confined to the patient whose
    active identity mapping matches the plan's patient. The recorded_by phone is
    the authoritative patient record's phone (409 if unbound).
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    try:
        plan = uow.medication_plans.get(body.medication_plan_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Medication plan not found")

    patient = authorize_patient_operation(
        ctx, policy, Operation.WRITE_MEDICATION_ADMINISTRATION, plan.patient_id, uow
    )
    if patient.phone is None:
        raise HTTPException(
            status_code=409,
            detail="Patient phone is required to record a medication administration",
        )

    cmd = RecordMedicationAdministration(
        medication_plan_id=plan.id,
        administered_at=body.administered_at or clock.now(),
        recorded_by=patient.phone,
        correlation_id=_correlation_id(request),
    )
    result = RecordMedicationAdministrationHandler(uow, events, clock, id_gen).handle(cmd)
    return RecordMedicationAdministrationResponse(
        medication_plan_id=str(result.medication_plan_id),
        patient_id=str(result.patient_id),
        administered_at=result.administered_at,
    )