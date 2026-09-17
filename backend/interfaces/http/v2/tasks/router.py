"""Care-task v2 routes (Gate 10H-B, Gate 10J-B).

THIN route layer. No business logic lives here.

    GET  /api/v2/care-tasks               → list tasks (patient, assignee, or facility queue)
    GET  /api/v2/care-tasks/{id}          → single-task detail retrieval
    POST /api/v2/care-tasks               → create an assigned task (with optional due_at)
    POST /api/v2/care-tasks/{id}/start    → transition task to IN_PROGRESS
    POST /api/v2/care-tasks/{id}/complete → complete a task (state machine)
    POST /api/v2/care-tasks/{id}/reassign → reassign task to another facility worker

Scoping:
- Clinicians require an active, facility-matching membership (and an active patient)
- Coordinators can query facility queues and reassign open/in_progress tasks within facility
- Field Health Workers (FHW) can list, start, and complete tasks assigned to them; they cannot create tasks or view/modify other workers' tasks
- Caregivers require a VERIFIED, non-expired relationship plus the READ_CARE_TASKS / COMPLETE_CARE_TASKS capability
- Patients have NO task read/write surface
"""

from __future__ import annotations

import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.application.commands import (
    CompleteCareTask,
    CreateCareTask,
    ReassignCareTask,
    StartCareTask,
)
from backend.application.ops.contracts import AuditAction
from backend.application.ports.clock import Clock
from backend.application.ports.events import DomainEventPublisher
from backend.application.ports.id_generation import IdGenerator
from backend.application.ports.unit_of_work import UnitOfWork
from backend.application.services.complete_care_task import CompleteCareTaskHandler
from backend.application.services.create_care_task import CreateCareTaskHandler
from backend.application.services.reassign_care_task import ReassignCareTaskHandler
from backend.application.services.start_care_task import StartCareTaskHandler
from backend.domain.entities import CareTaskStatus
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
    ReassignCareTaskRequest,
    ReassignCareTaskResponse,
    StartCareTaskResponse,
)
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    AuthorizationPolicy,
    Operation,
)
from backend.interfaces.http.v2.security.scoping import (
    assert_clinician_facility_context,
    authorize_or_403,
    authorize_patient_operation,
)

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
        due_at=task.due_at,
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
    patient_id: str | None = Query(default=None),
    assigned_to_me: bool = Query(default=False),
    assigned_to_user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100),
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CareTaskListResponse:
    """List care tasks by patient, by assignee, or across a facility queue."""
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    task_status: CareTaskStatus | None = None
    if status is not None:
        try:
            task_status = CareTaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid care task status: {status}")

    # Case A: Assignee-scoped query ("My Tasks" or target assignee)
    if assigned_to_me or assigned_to_user_id:
        target_assignee: _uuid.UUID
        if assigned_to_me:
            target_assignee = ctx.actor_id
        else:
            try:
                target_assignee = _uuid.UUID(assigned_to_user_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid assigned_to_user_id")

        if "field_health_worker" in ctx.roles and target_assignee != ctx.actor_id:
            raise HTTPException(
                status_code=403,
                detail="Field health workers may only view tasks assigned to themselves",
            )

        authorize_or_403(ctx, policy, Operation.READ_CARE_TASKS)
        facility_id = assert_clinician_facility_context(ctx, uow)

        tasks = uow.care_tasks.list_for_assignee(target_assignee, status=task_status)
        # Filter active patients in worker's facility to ensure no isolation leaks
        filtered_tasks = []
        for t in tasks:
            try:
                p = uow.patients.get(t.patient_id)
                if getattr(p, "active", True) and getattr(p, "facility_id", None) == facility_id:
                    filtered_tasks.append(t)
            except EntityNotFound:
                pass
        tasks = filtered_tasks[: min(limit, 200)]
        return CareTaskListResponse(
            patient_id=None,
            task_count=len(tasks),
            items=[_task_response(t) for t in tasks],
        )

    # Case B: Patient-scoped query
    if patient_id is not None:
        try:
            patient_uuid = _uuid.UUID(patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid patient_id")

        patient = authorize_patient_operation(
            ctx, policy, Operation.READ_CARE_TASKS, patient_uuid, uow
        )
        if not getattr(patient, "active", True):
            raise HTTPException(status_code=403, detail="Access denied")

        tasks = uow.care_tasks.list_for_patient(patient_uuid, status=task_status)
        if "field_health_worker" in ctx.roles:
            tasks = [t for t in tasks if t.assigned_to_user_id == ctx.actor_id]
        tasks = tasks[: min(limit, 200)]
        return CareTaskListResponse(
            patient_id=str(patient_uuid),
            task_count=len(tasks),
            items=[_task_response(t) for t in tasks],
        )

    # Case C: Facility-wide queue (Coordinator / Doctor)
    if "field_health_worker" in ctx.roles:
        raise HTTPException(
            status_code=403,
            detail="Field health workers cannot view the facility-wide queue",
        )

    authorize_or_403(ctx, policy, Operation.READ_CARE_TASKS)
    facility_id = assert_clinician_facility_context(ctx, uow)

    tasks = uow.care_tasks.list_for_facility(facility_id, status=task_status)
    filtered_tasks = []
    for t in tasks:
        try:
            p = uow.patients.get(t.patient_id)
            if getattr(p, "active", True):
                filtered_tasks.append(t)
        except EntityNotFound:
            pass
    tasks = filtered_tasks[: min(limit, 200)]
    return CareTaskListResponse(
        patient_id=None,
        task_count=len(tasks),
        items=[_task_response(t) for t in tasks],
    )


@tasks_router.get(
    "/{care_task_id}",
    response_model=CareTaskResponse,
    dependencies=[
        Depends(
            audit_dependency(
                action=AuditAction.READ,
                resource_type="patient.care_task",
                resource_id_from=lambda request: path_param(request, "care_task_id"),
                atomic=False,
            )
        )
    ],
)
async def get_care_task(
    request: Request,
    response: Response,
    care_task_id: str,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> CareTaskResponse:
    """Retrieve single care task details."""
    apply_rate_limit(request=request, response=response, tier=TIERS["read"], limiter=limiter, ctx=ctx)

    try:
        task_uuid = _uuid.UUID(care_task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid care_task_id")

    try:
        task = uow.care_tasks.get(task_uuid)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="Care task not found")

    patient = authorize_patient_operation(
        ctx, policy, Operation.READ_CARE_TASKS, task.patient_id, uow
    )
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Access denied")

    if "field_health_worker" in ctx.roles and task.assigned_to_user_id != ctx.actor_id:
        raise HTTPException(
            status_code=403,
            detail="Field health workers may only view tasks assigned to themselves",
        )

    return _task_response(task)


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
    """Create an assigned care task for a scoped patient."""
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
        due_at=body.due_at,
        correlation_id=_correlation_id(request),
    )
    result = CreateCareTaskHandler(uow, events, clock, id_gen).handle(cmd)
    task = uow.care_tasks.get(result.care_task_id)
    return _task_response(task)


@tasks_router.post(
    "/{care_task_id}/start",
    response_model=StartCareTaskResponse,
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
async def start_care_task(
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
) -> StartCareTaskResponse:
    """Transition a care task from OPEN to IN_PROGRESS."""
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
        ctx, policy, Operation.START_CARE_TASK, task.patient_id, uow
    )
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Access denied")

    if "field_health_worker" in ctx.roles and task.assigned_to_user_id != ctx.actor_id:
        raise HTTPException(
            status_code=403,
            detail="Field health workers may only start tasks assigned to them",
        )

    result = StartCareTaskHandler(uow, events, clock, id_gen).handle(
        StartCareTask(
            care_task_id=task_uuid,
            correlation_id=_correlation_id(request),
        )
    )
    return StartCareTaskResponse(
        care_task_id=str(result.care_task_id),
        status=result.status,
    )


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
    """Complete a care task (state machine OPEN/IN_PROGRESS → COMPLETED)."""
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

    if "field_health_worker" in ctx.roles and task.assigned_to_user_id != ctx.actor_id:
        raise HTTPException(
            status_code=403,
            detail="Field health workers may only complete tasks assigned to them",
        )

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


@tasks_router.post(
    "/{care_task_id}/reassign",
    response_model=ReassignCareTaskResponse,
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
async def reassign_care_task(
    request: Request,
    response: Response,
    care_task_id: str,
    body: ReassignCareTaskRequest,
    ctx: AuthenticatedContext = Depends(get_authenticated_context),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
    uow: UnitOfWork = Depends(get_unit_of_work),
    events: DomainEventPublisher = Depends(get_event_publisher),
    clock: Clock = Depends(get_clock),
    id_gen: IdGenerator = Depends(get_id_generator),
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> ReassignCareTaskResponse:
    """Reassign an OPEN or IN_PROGRESS care task to another worker in the same facility."""
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
        ctx, policy, Operation.REASSIGN_CARE_TASK, task.patient_id, uow
    )
    if not getattr(patient, "active", True):
        raise HTTPException(status_code=403, detail="Access denied")

    # Verify target assignee exists, is active, and is in the same facility
    try:
        new_assignee = uow.care_team_members.get(body.new_user_id)
    except EntityNotFound:
        raise HTTPException(status_code=404, detail="New assignee not found")

    if not getattr(new_assignee, "active", True):
        raise HTTPException(status_code=403, detail="New assignee membership is inactive")

    if getattr(new_assignee, "facility_id", None) != patient.facility_id:
        raise HTTPException(
            status_code=403,
            detail="New assignee is outside the patient's authorized facility",
        )

    result = ReassignCareTaskHandler(uow, events, clock, id_gen).handle(
        ReassignCareTask(
            care_task_id=task_uuid,
            new_user_id=body.new_user_id,
            correlation_id=_correlation_id(request),
        )
    )
    return ReassignCareTaskResponse(
        care_task_id=str(result.care_task_id),
        assigned_to_user_id=str(result.assigned_to_user_id),
        status=result.status,
    )