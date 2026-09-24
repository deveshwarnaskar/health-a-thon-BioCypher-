"""SqlAlchemyMedicationPlanRepository (Gate 05).

Concrete infrastructure implementation of MedicationPlanRepository port.
Enforces multi-tenant scoping and reconstructs clinician-authored MedicationPlans.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import MedicationPlan
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import medication_plan_to_domain, medication_plan_to_model
from ..models.plan_models import MedicationPlanModel


class SqlAlchemyMedicationPlanRepository:
    """SQLAlchemy-backed repository for MedicationPlan aggregates."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyMedicationPlanRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, plan: MedicationPlan) -> None:
        model = medication_plan_to_model(plan, self.tenant_id)
        self.session.add(model)

    def get(self, plan_id: UUID) -> MedicationPlan:
        stmt = select(MedicationPlanModel).where(
            MedicationPlanModel.id == plan_id,
            MedicationPlanModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"medication_plan {plan_id} not found")
        return medication_plan_to_domain(model)

    def list(self) -> list[MedicationPlan]:
        stmt = (
            select(MedicationPlanModel)
            .where(MedicationPlanModel.tenant_id == self.tenant_id)
            .order_by(MedicationPlanModel.created_at, MedicationPlanModel.id)
        )
        return [medication_plan_to_domain(m) for m in self.session.scalars(stmt).all()]

    def list_for_patient(self, patient_id: UUID) -> list[MedicationPlan]:
        stmt = (
            select(MedicationPlanModel)
            .where(
                MedicationPlanModel.patient_id == patient_id,
                MedicationPlanModel.tenant_id == self.tenant_id,
            )
            .order_by(MedicationPlanModel.created_at, MedicationPlanModel.id)
        )
        return [medication_plan_to_domain(m) for m in self.session.scalars(stmt).all()]
