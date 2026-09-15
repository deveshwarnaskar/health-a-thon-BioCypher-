"""SqlAlchemyIdentityPatientMappingRepository (Gate 08).

Concrete infrastructure implementation of the IdentityPatientMappingRepository
port. All queries are tenant-scoped. Identity lookups return ``None`` on
absence (the authorization policy treats absence as a denial).
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import IdentityPatientMapping
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import (
    identity_patient_mapping_to_domain,
    identity_patient_mapping_to_model,
)
from ..models.identity_models import IdentityPatientMappingModel


class SqlAlchemyIdentityPatientMappingRepository:
    """SQLAlchemy-backed repository for IdentityPatientMapping entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyIdentityPatientMappingRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, mapping: IdentityPatientMapping) -> None:
        model = identity_patient_mapping_to_model(mapping, self.tenant_id)
        self.session.add(model)

    def save(self, mapping: IdentityPatientMapping) -> None:
        stmt = select(IdentityPatientMappingModel).where(
            IdentityPatientMappingModel.id == mapping.id,
            IdentityPatientMappingModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"identity mapping {mapping.id} not found")
        model.active = mapping.active
        model.updated_at = mapping.updated_at

    def get(self, mapping_id: UUID) -> IdentityPatientMapping:
        stmt = select(IdentityPatientMappingModel).where(
            IdentityPatientMappingModel.id == mapping_id,
            IdentityPatientMappingModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"identity mapping {mapping_id} not found")
        return identity_patient_mapping_to_domain(model)

    def get_by_user_id(self, user_id: UUID) -> IdentityPatientMapping | None:
        stmt = select(IdentityPatientMappingModel).where(
            IdentityPatientMappingModel.tenant_id == self.tenant_id,
            IdentityPatientMappingModel.user_id == user_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            return None
        return identity_patient_mapping_to_domain(model)

    def get_by_patient_id(self, patient_id: UUID) -> IdentityPatientMapping | None:
        stmt = select(IdentityPatientMappingModel).where(
            IdentityPatientMappingModel.tenant_id == self.tenant_id,
            IdentityPatientMappingModel.patient_id == patient_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            return None
        return identity_patient_mapping_to_domain(model)

    def list(self) -> list[IdentityPatientMapping]:
        stmt = (
            select(IdentityPatientMappingModel)
            .where(IdentityPatientMappingModel.tenant_id == self.tenant_id)
            .order_by(IdentityPatientMappingModel.created_at)
        )
        return [identity_patient_mapping_to_domain(m) for m in self.session.scalars(stmt).all()]