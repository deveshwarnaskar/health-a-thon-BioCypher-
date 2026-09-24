"""SqlAlchemyGlucoseObservationRepository (Gate 05).

Concrete infrastructure implementation of GlucoseObservationRepository port.
Enforces multi-tenant scoping and patient boundary isolation.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import GlucoseObservation
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import (
    glucose_observation_to_domain,
    glucose_observation_to_model,
)
from ..models.observation_models import GlucoseObservationModel


class SqlAlchemyGlucoseObservationRepository:
    """SQLAlchemy-backed repository for GlucoseObservation entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyGlucoseObservationRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, observation: GlucoseObservation) -> None:
        model = glucose_observation_to_model(observation, self.tenant_id)
        self.session.add(model)

    def get(self, observation_id: UUID) -> GlucoseObservation:
        stmt = select(GlucoseObservationModel).where(
            GlucoseObservationModel.id == observation_id,
            GlucoseObservationModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"glucose_observation {observation_id} not found")
        return glucose_observation_to_domain(model)

    def list_for_patient(self, patient_id: UUID) -> list[GlucoseObservation]:
        stmt = (
            select(GlucoseObservationModel)
            .where(
                GlucoseObservationModel.patient_id == patient_id,
                GlucoseObservationModel.tenant_id == self.tenant_id,
            )
            .order_by(GlucoseObservationModel.taken_at)
        )
        return [glucose_observation_to_domain(m) for m in self.session.scalars(stmt).all()]
