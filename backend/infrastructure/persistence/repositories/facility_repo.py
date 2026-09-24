"""SqlAlchemyFacilityRepository (Gate 10K-B).

Concrete infrastructure implementation of FacilityRepository port.
Enforces multi-tenant scoping and reconstructs pure domain Facility entities.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import Facility
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import facility_to_domain, facility_to_model
from ..models.tenant_models import FacilityModel


class SqlAlchemyFacilityRepository:
    """SQLAlchemy-backed repository for Facility entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyFacilityRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, facility: Facility) -> None:
        model = facility_to_model(facility, self.tenant_id)
        self.session.add(model)

    def get(self, facility_id: UUID) -> Facility:
        stmt = select(FacilityModel).where(
            FacilityModel.id == facility_id,
            FacilityModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"facility {facility_id} not found")
        return facility_to_domain(model)

    def save(self, facility: Facility) -> None:
        stmt = select(FacilityModel).where(
            FacilityModel.id == facility.id,
            FacilityModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"facility {facility.id} not found")
        model.name = facility.name
        model.active = facility.active

    def list(self) -> list[Facility]:
        stmt = (
            select(FacilityModel)
            .where(FacilityModel.tenant_id == self.tenant_id)
            .order_by(FacilityModel.created_at)
        )
        return [facility_to_domain(m) for m in self.session.scalars(stmt).all()]
