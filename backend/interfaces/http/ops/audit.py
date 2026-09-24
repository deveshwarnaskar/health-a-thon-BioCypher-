"""Gate 09 — atomic audit dependency (HTTP).

FastAPI route dependencies that record compliance events without leaking PHI:

- The SUCCESS record is inserted into the SAME unit-of-work session that the
  route's business handler commits, so a request that persists its domain work
  carries its audit row in the identical transaction (atomic by construction).
- Read-only/standalone routes (``atomic=False``) commit their own record.
- If the route raises, a separate FAILED record is written from a fresh
  tenant-bound session; exception detail is NEVER included (no stack traces,
  paths, or PHI in ``reason``).

``resource_id_from`` is an optional callable used to extract the pre-execution
resource identifier (e.g. the body's patient_id) into the audit row; it must
return a string or None.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import Depends, Request

from backend.application.ops.contracts import AuditAction, AuditEvent, AuditOutcome
from backend.infrastructure.persistence.ops.audit_store import SqlAlchemyAuditStore
from backend.infrastructure.config.database import create_session_factory
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.interfaces.http.dependencies import (
    _get_engine,
    get_authenticated_context,
    get_db_url,
    get_unit_of_work,
)
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext

logger = logging.getLogger(__name__)

ResourceIdFn = Callable[[Request], Awaitable[str | None]]


async def _resolve_resource_id(fn: ResourceIdFn | None, request: Request) -> str | None:
    if fn is None:
        return None
    result = fn(request)
    if hasattr(result, "__await__"):
        return await result
    return result


async def json_field(request: Request, field: str) -> str | None:
    """Best-effort extraction of one top-level JSON field for audit metadata."""
    try:
        raw = await request.json()
    except Exception:
        return None
    value = raw.get(field) if isinstance(raw, dict) else None
    return str(value) if value is not None else None


async def path_param(request: Request, name: str) -> str | None:
    """Best-effort extraction of a path parameter for audit metadata."""
    value = request.path_params.get(name)
    return str(value) if value is not None else None


def _actor_type(ctx: AuthenticatedContext) -> str:
    roles = set(ctx.roles)
    if "admin" in roles:
        return "ADMIN"
    if "patient" in roles:
        return "PATIENT"
    if "caregiver" in roles:
        return "CAREGIVER"
    return "CLINICIAN"


def _base_event(
    request: Request,
    ctx: AuthenticatedContext,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: str,
    reason: str | None,
) -> AuditEvent:
    correlation_id = getattr(request.state, "correlation_id", "") or ""
    return AuditEvent(
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        actor_type=_actor_type(ctx),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id or "",
        occurred_at=datetime.now(timezone.utc),
        correlation_id=correlation_id,
        request_id=f"{correlation_id}:{str(uuid.uuid4())[:8]}",
        source_ip=request.client.host if request.client else None,
        outcome=outcome,
        reason=reason,
    )


def _write_failure_event(
    request: Request,
    ctx: AuthenticatedContext,
    action: str,
    resource_type: str,
    resource_id: str | None,
) -> None:
    event = _base_event(
        request,
        ctx,
        action,
        resource_type,
        resource_id,
        outcome=AuditOutcome.FAILED.value,
        reason="request processing failed",
    )
    engine = _get_engine(get_db_url())
    uow = SqlAlchemyUnitOfWork(create_session_factory(engine), ctx.tenant_id)
    try:
        SqlAlchemyAuditStore(uow.session, ctx.tenant_id).record(event)
        uow.session.commit()
    except Exception:
        logger.exception("failed to record failure audit event")
        uow.session.rollback()
    finally:
        uow.close()


def audit_dependency(
    *,
    action: str | AuditAction,
    resource_type: str,
    resource_id_from: ResourceIdFn | None = None,
    atomic: bool = True,
):
    """Build a FastAPI generator dependency that records one audit event.

    Usage::

        @router.post("/...")
        async def route(
            ...,
            _audit: None = Depends(
                audit_dependency(
                    action=AuditAction.CREATE,
                    resource_type="patient.observation",
                    resource_id_from=lambda request: _patient_id_from_body(request),
                )
            ),
        ):
    """

    action_value = action.value if isinstance(action, AuditAction) else str(action)
    resource_id: str | None = None

    async def dependency(
        request: Request,
        uow: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
        ctx: AuthenticatedContext = Depends(get_authenticated_context),
    ) -> Any:
        nonlocal resource_id
        resource_id = await _resolve_resource_id(resource_id_from, request)

        event = _base_event(
            request,
            ctx,
            action_value,
            resource_type,
            resource_id,
            outcome=AuditOutcome.SUCCESS.value,
            reason=None,
        )
        SqlAlchemyAuditStore(uow.session, ctx.tenant_id).record(event)
        if not atomic:
            # Read-path/standalone audits fail OPEN: an unavailable audit sink
            # must never take down an authentication or read endpoint.
            try:
                uow.session.commit()
            except Exception:
                logger.exception("failed to record read-path audit event (request continues)")
                uow.session.rollback()
        try:
            yield
        except Exception:
            _write_failure_event(request, ctx, action_value, resource_type, resource_id)
            raise

    return dependency


__all__ = ["audit_dependency"]