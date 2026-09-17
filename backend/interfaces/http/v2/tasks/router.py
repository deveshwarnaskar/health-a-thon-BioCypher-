"""Care-task v2 routes (Gate 10H-B).

THIN route layer. No business logic lives here.

    GET  /api/v2/care-tasks?patient_id=… → patient-scoped task list
    POST /api/v2/care-tasks              → create an assigned task
    POST /api/v2/care-tasks/{id}/complete → complete a task (state machine)

Scoping: - clinicians require an active, facility-matching membership (and an
           active patient)
         - caregivers require a VERIFIED, non-expired relationship plus the
           READ_CARE_TASKS / COMPLETE_CARE_TASKS capability
         - patients have NO task read/write surface in this gate
The patient_id is always resolved and authorized — never trusted blindly.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.application.commands import CompleteCareTask, CreateCareTask
from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.complete_care_task import CompleteCareTaskHandler
from backend.application.services.create_care_task import CreateCareTaskHandler
from backend.domain.exceptions import EntityNotFound
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
    CareTaskListResponse,
    CareTaskResponse,
    CompleteCareTaskResponse,
    CreateCareTaskRequest,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import authorize_patient_operation

tasks_router = APIRouter()


def _correlation_id(request: Request) -> _uuid.UUID | None:
    raw = getattr(request.state, "correlation_id", None)
    if not raw:
        return None
    try:
        return _uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _task_response(task) -> CareTaskResponse:
    return CareTaskResponse(
        care_task_id=str(task.id),
        patient_id=str(task.patient_id),
        assigned_to_user_id=str(task.assigned_to_user_id),
        description=task.description,
        status=task.status.value,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


@tasks_router.get(
    "",
    response_model=CareTaskListResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="patient.care_task_list",
                resource_id_from=lambda request: request.query_params.get("patient_id"),
                atomic=False,
            )
        )
    ],
)
async def list_care_tasks(
    request: Request,
    response: Response,
    patient_id: str,
    limit: int = 100,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CareTaskListResponse:
    """List care tasks for ONE scoped patient.

    Patient role is denied (no task surface in this gate). Caregivers require
    READ_CARE_TASKS; clinicians require an active facility-matching membership
    and an active patient.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    try:
        patient_uuid = _uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid patient_id")

    patient = authorize_patient_operation(
        ctx, policy, Operation.READ_CARE_TASKS, patient_uuid, uow
    )
    if not getattr(patient, "active", True):
        # Deactivated-patient invariant: deactivated patients never surface
        # through clinician reads.
        raise HTTPException(status_code=403, detail="Access denied")

    tasks = uow.care_tasks.list_for_patient(patient_uuid)
    tasks = tasks[: min(limit, 200)]
    return CareTaskListResponse(
        patient_id=str(patient_uuid),
        task_count=len(tasks),
        items=[_task_response(t) for t in tasks],
    )


@tasks_router.post(
    "",
    response_model=CareTaskResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.CREATE,
                resource_type="patient.care_task",
                resource_id_from=lambda request: json_field(request, "patient_id"),
            )
        )
    ],
)
async def create_care_task(
    request: Request,
    response: Response,
    body: CreateCareTaskRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CareTaskResponse:
    """Create an assigned care task for a scoped patient.

    Assigner authority comes from the role matrix (doctor/nurse/dietitian/
    care_coordinator) plus facility scoping. Caregivers and patients cannot
    create tasks (unlisted operations are denied).
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    patient = authorize_patient_operation(
        ctx, policy, Operation.CREATE_CARE_TASK, body.patient_id, uow
    )
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Access denied")

    cmd = CreateCareTask(
        patient_id=body.patient_id,
        assigned_to_user_id=body.assigned_to_user_id,
        description=body.description,
        correlation_id=_correlation_id(request),
    )
    result = CreateCareTaskHandler(uow, events, clock, id_gen).handle(cmd)
    task = uow.care_tasks.get(result.care_task_id)
    return _task_response(task)


@tasks_router.post(
    "/{care_task_id}/complete",
    response_model=CompleteCareTaskResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.UPDATE,
                resource_type="patient.care_task",
                resource_id_from=lambda request: path_param(request, "care_task_id"),
            )
        )
    ],
)
async def complete_care_task(
    request: Request,
    response: Response,
    care_task_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CompleteCareTaskResponse:
    """Complete a care task (state machine OPEN/IN_PROGRESS → COMPLETED).

    The task's patient is resolved and authorized first; a caregiver requires
    the COMPLETE_CARE_TASKS capability, clinicians an active facility-matching
    membership. Repeated completion on a completed task → 409 INVALID_STATE.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["clinical_write"], limiter=limiter, ctx=ctx)

    try:
        task_uuid = _uuid.UUID(care_task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid care_task_id")

    try:
        task = uow.care_tasks.get(task_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Care task not found")

    patient = authorize_patient_operation(
        ctx, policy, Operation.COMPLETE_CARE_TASK, task.patient_id, uow
    )
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Access denied")

    result = CompleteCareTaskHandler(uow, events, clock, id_gen).handle(
        CompleteCareTask(
            care_task_id=task_uuid,
            correlation_id=_correlation_id(request),
        )
    )
    return CompleteCareTaskResponse(
        care_task_id=str(result.care_task_id),
        status=result.status,
        completed_at=result.completed_at,
    )