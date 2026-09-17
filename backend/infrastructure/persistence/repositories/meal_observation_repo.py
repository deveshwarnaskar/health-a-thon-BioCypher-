"""SqlAlchemyMealObservationRepository (Gate 05).

Concrete infrastructure implementation of MealObservationRepository port.
Enforces multi-tenant scoping, volumetric katori reconstruction, and clinical asymmetry persistence.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import MealObservation
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import meal_observation_to_domain, meal_observation_to_model
from ..models.observation_models import MealObservationModel


class SqlAlchemyMealObservationRepository:
    """SQLAlchemy-backed repository for MealObservation entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyMealObservationRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, observation: MealObservation) -> None:
        model = meal_observation_to_model(observation, self.tenant_id)
        self.session.add(model)

    def get(self, observation_id: UUID) -> MealObservation:
        stmt = select(MealObservationModel).where(
            MealObservationModel.id == observation_id,
            MealObservationModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"meal_observation {observation_id} not found")
        return meal_observation_to_domain(model)

    def save(self, observation: MealObservation) -> None:
        stmt = select(MealObservationModel).where(
            MealObservationModel.id == observation.id,
            MealObservationModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"meal_observation {observation.id} not found")
        model.description = observation.description
        model.portion_food_key = observation.portion.food_key if observation.portion else None
        model.portion_volume_ml = observation.portion.katori.volume_ml if observation.portion else None
        model.portion_quantity = observation.portion.quantity if observation.portion else None
        model.carbs_grams = observation.carbs_grams
        model.glycemic_index = observation.glycemic_index
        model.confirmation = observation.confirmation.value
        model.confirmed_by = observation.confirmed_by.value if observation.confirmed_by else None

    def list_for_patient(self, patient_id: UUID) -> list[MealObservation]:
        stmt = (
            select(MealObservationModel)
            .where(
                MealObservationModel.patient_id == patient_id,
                MealObservationModel.tenant_id == self.tenant_id,
            )
            .order_by(MealObservationModel.recorded_at)
        )
        return [meal_observation_to_domain(m) for m in self.session.scalars(stmt).all()]
