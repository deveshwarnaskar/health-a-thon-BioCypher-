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

import base64
import uuid as _uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.application.commands import (
    ConfirmMealObservation,
    CreateMedicationPlan,
    GenerateAIReviewArtifact,
    GenerateReport,
    IngestGlucoseReading,
    LogMealDraft,
    RecordMedicationAdministration,
    ReviewAIArtifact,
    UploadDocument,
)
from backend.application.exceptions import (
    AIGenerationFailed,
    InactivePatientError,
    InvalidReportFormatError,
    ReviewerNotAuthorized,
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
from backend.application.services.evidence_builder import EvidenceBuilder
from backend.application.services.generate_ai_artifact import GenerateAIReviewArtifactHandler
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
from backend.application.services.generate_report import GenerateReportHandler
from backend.application.services.upload_document import UploadDocumentHandler

from backend.application.dtos.clinical import ClinicalGlucoseRecord, ClinicalMealRecord
from backend.domain.entities import DocumentKind
from backend.domain.exceptions import EntityNotFound, InvalidStateTransition
from backend.domain.value_objects import GlucoseValue, KatoriVolume, MealPortion, ReadingTag
from backend.infrastructure.ai import DeterministicDemoProvider, ProductionModelProvider
from config.settings import Settings
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_authorization_policy,
    get_clock,
    get_event_publisher,
    get_id_generator,
    get_object_storage,
    get_unit_of_work,
)
from backend.interfaces.http.ops.audit import audit_dependency, json_field, path_param
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.schemas import (
    AIArtifactDetailResponse,
    AIArtifactListResponse,
    AIArtifactResponse,
    ClinicalObservationFeedResponse,
    ConfirmMealRequest,
    ConfirmMealResponse,
    CreateMedicationPlanRequest,
    CreateMedicationPlanResponse,
    DocumentDownloadResponse,
    DocumentReferenceListResponse,
    DocumentReferenceResponse,
    GenerateAIArtifactRequest,
    GenerateAIArtifactResponse,
    GenerateReportRequest,
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
    UploadDocumentRequest,
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
    "/ai-artifacts/generate",
    response_model=GenerateAIArtifactResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="ai_artifact.generate",
                resource_id_from=None,
            )
        )
    ],
)
async def generate_ai_artifact(
    request: Request,
    response: Response,
    body: GenerateAIArtifactRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> GenerateAIArtifactResponse:
    """Licensed clinician generates an AI review artifact draft.

    Enforces:
    - Operation.GENERATE_AI_ARTIFACT (doctor/nurse/dietitian only; admin/coordinator/fhw/patient/caregiver denied)
    - Patient facility matches clinician active facility
    - Patient is active
    - Deterministic EvidenceBuilder compiles authorized evidence
    - Model output is strictly unapproved draft in PENDING_REVIEW
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["ai"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.GENERATE_AI_ARTIFACT)

    try:
        patient = uow.patients.get(body.patient_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not getattr(patient, "active", True):
        raise HTTPException(status_code=400, detail="Patient is deactivated")

    assert_authorized_clinician_facility(ctx, uow, patient)

    settings = Settings()
    if settings.ai.provider == "gemini" and settings.ai.api_key:
        provider = ProductionModelProvider(
            api_key=settings.ai.api_key,
            model_name=settings.ai.model or "gemini-1.5-flash",
        )
    else:
        provider = DeterministicDemoProvider()

    cmd = GenerateAIReviewArtifact(
        patient_id=body.patient_id,
        artifact_kind="clinical_summary",
        context=body.context,
        correlation_id=_correlation_id(request),
        tenant_id=ctx.tenant_id,
        requester_user_id=ctx.actor_id,
        task_type=body.task_type,
        model_name=getattr(provider, "model_name", None),
    )

    try:
        result = GenerateAIReviewArtifactHandler(
            uow=uow,
            events=events,
            provider=provider,
            clock=clock,
            id_gen=id_gen,
            evidence_builder=EvidenceBuilder(),
        ).handle(cmd)
    except AIGenerationFailed as e:
        if e.error_code == "CREDENTIALS_MISSING":
            raise HTTPException(status_code=503, detail="AI provider credentials missing")
        elif e.error_code == "TIMEOUT":
            raise HTTPException(status_code=504, detail="AI provider timed out")
        elif e.error_code == "MALFORMED_OUTPUT":
            raise HTTPException(status_code=502, detail="AI provider returned malformed output")
        elif e.error_code == "PROVIDER_4XX":
            raise HTTPException(status_code=400, detail="AI provider rejected request")
        else:
            raise HTTPException(status_code=502, detail=str(e))

    artifact = uow.ai_artifacts.get(result.artifact_id)
    return GenerateAIArtifactResponse(
        artifact_id=str(result.artifact_id),
        patient_id=str(result.patient_id),
        state=result.state,
        summary=result.summary,
        model_name=artifact.model_name,
        evidence_hash=artifact.evidence_hash,
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
    try:
        result = ReviewAIArtifactHandler(uow, events, clock, id_gen).handle(cmd)
    except InvalidStateTransition as e:
        raise HTTPException(status_code=409, detail=f"Review state conflict: {e}")
    except ReviewerNotAuthorized as e:
        raise HTTPException(status_code=403, detail=str(e))

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
    response_model=AIArtifactDetailResponse,
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
) -> AIArtifactDetailResponse:
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
    return AIArtifactDetailResponse(
        artifact_id=str(result.artifact_id),
        patient_id=str(result.patient_id),
        artifact_kind=result.artifact_kind,
        state=result.state,
        summary=result.summary,
        created_at=result.created_at,
        model_name=artifact.model_name,
        evidence_hash=artifact.evidence_hash,
        original_summary=artifact.original_summary,
        reviewed_by_user_id=str(artifact.reviewed_by_user_id) if artifact.reviewed_by_user_id else None,
        reviewed_at=artifact.reviewed_at,
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


# ─── Reports & Documents (Gate 10N) ─────────────────────────────────────────


@clinical_router.post(
    "/reports/generate",
    response_model=DocumentReferenceResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="clinical.report",
                resource_id_from=lambda request: json_field(request, "patient_id"),
            )
        )
    ],
)
async def generate_report(
    request: Request,
    response: Response,
    body: GenerateReportRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    storage=Depends(get_object_storage),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> DocumentReferenceResponse:
    """Generate a server-authoritative clinical or patient report (PDF / PNG).

    Enforces:
    - Operation.GENERATE_REPORT (doctor/nurse/dietitian only; proxy/unauthorized denied)
    - Patient facility matches clinician active facility
    - Patient is active (deactivated -> 403)
    - Deterministic ReportBuilder compilation
    - Output saved to private S3 object storage
    - DocumentReference record created with RLS
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    authorize_or_403(ctx, policy, Operation.GENERATE_REPORT)

    try:
        patient = uow.patients.get(body.patient_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Patient is deactivated")

    assert_authorized_clinician_facility(ctx, uow, patient)

    cmd = GenerateReport(
        patient_id=body.patient_id,
        tenant_id=ctx.tenant_id,
        requester_user_id=ctx.actor_id,
        report_type=body.report_type,
        format=body.format,
        facility_id=patient.facility_id,
        correlation_id=_correlation_id(request),
    )

    try:
        doc_ref = GenerateReportHandler(uow, storage, events, clock, id_gen).handle(cmd)
    except InactivePatientError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidReportFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    try:
        download_url = storage.generate_presigned_url(doc_ref.storage_key, expires_in=300)
    except Exception:
        download_url = None

    return DocumentReferenceResponse(
        id=str(doc_ref.id),
        patient_id=str(doc_ref.patient_id),
        kind=doc_ref.kind.value if hasattr(doc_ref.kind, "value") else str(doc_ref.kind),
        filename=doc_ref.filename,
        mime_type=doc_ref.mime_type,
        file_size_bytes=doc_ref.file_size_bytes,
        created_at=doc_ref.created_at,
        download_url=download_url,
    )


@clinical_router.get(
    "/patients/{patient_id}/documents",
    response_model=DocumentReferenceListResponse,
)
async def list_patient_documents(
    request: Request,
    response: Response,
    patient_id: str,
    kind: str | None = None,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    storage=Depends(get_object_storage),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> DocumentReferenceListResponse:
    """List document references for an authorized patient."""
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    if patient_id.lower() == "me":
        mapping = uow.identity_mappings.get_by_user_id(ctx.actor_id)
        if mapping is None or not mapping.active:
            raise HTTPException(status_code=403, detail="No active patient mapping found")
        patient_uuid = mapping.patient_id
    else:
        try:
            patient_uuid = _uuid.UUID(patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid patient_id")

    patient = authorize_patient_operation(
        ctx, policy, Operation.READ_DOCUMENTS, patient_uuid, uow
    )
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Patient is deactivated")

    doc_kind = None
    if kind:
        try:
            doc_kind = DocumentKind(kind.strip().lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid document kind: {kind}")

    docs = uow.document_references.list_for_patient(patient_uuid, kind=doc_kind)

    items = []
    for d in docs:
        try:
            url = storage.generate_presigned_url(d.storage_key, expires_in=300)
        except Exception:
            url = None
        items.append(
            DocumentReferenceResponse(
                id=str(d.id),
                patient_id=str(d.patient_id),
                kind=d.kind.value if hasattr(d.kind, "value") else str(d.kind),
                filename=d.filename,
                mime_type=d.mime_type,
                file_size_bytes=d.file_size_bytes,
                created_at=d.created_at,
                download_url=url,
            )
        )

    return DocumentReferenceListResponse(total=len(items), items=items)


@clinical_router.get(
    "/documents/{document_id}",
    response_model=DocumentReferenceResponse,
)
async def get_document_reference(
    request: Request,
    response: Response,
    document_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    storage=Depends(get_object_storage),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> DocumentReferenceResponse:
    """Retrieve metadata for a specific document reference."""
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    try:
        doc_uuid = _uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document_id")

    try:
        doc_ref = uow.document_references.get(doc_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Document not found")

    patient = authorize_patient_operation(
        ctx, policy, Operation.READ_DOCUMENTS, doc_ref.patient_id, uow
    )
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Patient is deactivated")

    try:
        url = storage.generate_presigned_url(doc_ref.storage_key, expires_in=300)
    except Exception:
        url = None

    return DocumentReferenceResponse(
        id=str(doc_ref.id),
        patient_id=str(doc_ref.patient_id),
        kind=doc_ref.kind.value if hasattr(doc_ref.kind, "value") else str(doc_ref.kind),
        filename=doc_ref.filename,
        mime_type=doc_ref.mime_type,
        file_size_bytes=doc_ref.file_size_bytes,
        created_at=doc_ref.created_at,
        download_url=url,
    )


@clinical_router.get(
    "/documents/{document_id}/download",
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="clinical.document",
                resource_id_from=lambda request: path_param(request, "document_id"),
                atomic=False,
            )
        )
    ],
)
async def download_document(
    request: Request,
    response: Response,
    document_id: str,
    signed_url: bool = False,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    storage=Depends(get_object_storage),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
):
    """Download document payload directly or generate a short-lived presigned URL."""
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    try:
        doc_uuid = _uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document_id")

    try:
        doc_ref = uow.document_references.get(doc_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Document not found")

    patient = authorize_patient_operation(
        ctx, policy, Operation.READ_DOCUMENTS, doc_ref.patient_id, uow
    )
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Patient is deactivated")

    if signed_url:
        try:
            url = storage.generate_presigned_url(doc_ref.storage_key, expires_in=300)
        except KeyError:
            raise HTTPException(status_code=404, detail="Document payload not found in storage")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate signed url: {e}")
        return DocumentDownloadResponse(
            download_url=url,
            expires_in=300,
            filename=doc_ref.filename,
            mime_type=doc_ref.mime_type,
        )

    try:
        payload = storage.get(doc_ref.storage_key)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document payload not found in storage")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve document: {e}")

    return Response(
        content=payload,
        media_type=doc_ref.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{doc_ref.filename}"',
            "Content-Type": doc_ref.mime_type,
        },
    )


@clinical_router.post(
    "/patients/{patient_id}/documents/upload",
    response_model=DocumentReferenceResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="clinical.document",
                resource_id_from=lambda request: path_param(request, "patient_id"),
            )
        )
    ],
)
async def upload_document(
    request: Request,
    response: Response,
    patient_id: str,
    body: UploadDocumentRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    storage=Depends(get_object_storage),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> DocumentReferenceResponse:
    """Upload an external document or chart image to private storage."""
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    patient = authorize_patient_operation(
        ctx, policy, Operation.UPLOAD_DOCUMENT, patient_uuid, uow
    )
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Patient is deactivated")

    try:
        doc_kind = DocumentKind(body.kind.strip().lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid document kind: {body.kind}")

    try:
        content = base64.b64decode(body.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed base64 document content")

    cmd = UploadDocument(
        patient_id=patient_uuid,
        tenant_id=ctx.tenant_id,
        uploader_user_id=ctx.actor_id,
        facility_id=patient.facility_id,
        filename=body.filename,
        mime_type=body.mime_type,
        payload=content,
        kind=doc_kind,
        correlation_id=_correlation_id(request),
    )

    try:
        doc_ref = UploadDocumentHandler(uow, storage, clock, id_gen).handle(cmd)
    except InactivePatientError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        if "exceeds maximum" in str(e).lower():
            raise HTTPException(status_code=413, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    try:
        url = storage.generate_presigned_url(doc_ref.storage_key, expires_in=300)
    except Exception:
        url = None

    return DocumentReferenceResponse(
        id=str(doc_ref.id),
        patient_id=str(doc_ref.patient_id),
        kind=doc_ref.kind.value if hasattr(doc_ref.kind, "value") else str(doc_ref.kind),
        filename=doc_ref.filename,
        mime_type=doc_ref.mime_type,
        file_size_bytes=doc_ref.file_size_bytes,
        created_at=doc_ref.created_at,
        download_url=url,
    )