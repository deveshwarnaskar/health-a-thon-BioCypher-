"""SqlAlchemyCareTaskRepository (Gate 05).

Concrete infrastructure implementation of CareTaskRepository port.
Enforces multi-tenant scoping and persists care task state transitions.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import CareTask
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import care_task_to_domain, care_task_to_model
from ..models.plan_models import CareTaskModel


class SqlAlchemyCareTaskRepository:
    """SQLAlchemy-backed repository for CareTask entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyCareTaskRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, task: CareTask) -> None:
        model = care_task_to_model(task, self.tenant_id)
        self.session.add(model)

    def get(self, task_id: UUID) -> CareTask:
        stmt = select(CareTaskModel).where(
            CareTaskModel.id == task_id,
            CareTaskModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"care_task {task_id} not found")
        return care_task_to_domain(model)

    def save(self, task: CareTask) -> None:
        stmt = select(CareTaskModel).where(
            CareTaskModel.id == task.id,
            CareTaskModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"care_task {task.id} not found")
        model.description = task.description
        model.status = task.status.value
        model.completed_at = task.completed_at

    def list_for_patient(self, patient_id: UUID) -> list[CareTask]:
        stmt = (
            select(CareTaskModel)
            .where(
                CareTaskModel.patient_id == patient_id,
                CareTaskModel.tenant_id == self.tenant_id,
            )
            .order_by(CareTaskModel.created_at)
        )
        return [care_task_to_domain(m) for m in self.session.scalars(stmt).all()]
