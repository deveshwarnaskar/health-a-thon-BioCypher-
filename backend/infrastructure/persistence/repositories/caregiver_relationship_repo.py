"""SqlAlchemyCaregiverRelationshipRepository (Gate 08).

Concrete infrastructure implementation of the CaregiverRelationshipRepository
port. All queries are tenant-scoped. Reconstructs pure domain entities.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import (
    CaregiverRelationship,
    CaregiverRelationshipStatus,
)
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import (
    caregiver_relationship_to_domain,
    caregiver_relationship_to_model,
)
from ..models.identity_models import CaregiverRelationshipModel


class SqlAlchemyCaregiverRelationshipRepository:
    """SQLAlchemy-backed repository for CaregiverRelationship entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyCaregiverRelationshipRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, relationship: CaregiverRelationship) -> None:
        model = caregiver_relationship_to_model(relationship, self.tenant_id)
        self.session.add(model)

    def get(self, relationship_id: UUID) -> CaregiverRelationship:
        stmt = select(CaregiverRelationshipModel).where(
            CaregiverRelationshipModel.id == relationship_id,
            CaregiverRelationshipModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"caregiver relationship {relationship_id} not found")
        return caregiver_relationship_to_domain(model)

    def save(self, relationship: CaregiverRelationship) -> None:
        stmt = select(CaregiverRelationshipModel).where(
            CaregiverRelationshipModel.id == relationship.id,
            CaregiverRelationshipModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"caregiver relationship {relationship.id} not found")
        model.relationship_label = relationship.relationship
        model.status = relationship.status.value
        model.capabilities = sorted(relationship.capabilities)
        model.verified_at = relationship.verified_at
        model.revoked_at = relationship.revoked_at
        model.expires_at = relationship.expires_at
        model.updated_at = relationship.updated_at

    def list_for_caregiver(self, caregiver_user_id: UUID) -> list[CaregiverRelationship]:
        stmt = (
            select(CaregiverRelationshipModel)
            .where(
                CaregiverRelationshipModel.tenant_id == self.tenant_id,
                CaregiverRelationshipModel.caregiver_user_id == caregiver_user_id,
            )
            .order_by(CaregiverRelationshipModel.created_at)
        )
        return [caregiver_relationship_to_domain(m) for m in self.session.scalars(stmt).all()]

    def list_for_patient(self, patient_id: UUID) -> list[CaregiverRelationship]:
        stmt = (
            select(CaregiverRelationshipModel)
            .where(
                CaregiverRelationshipModel.tenant_id == self.tenant_id,
                CaregiverRelationshipModel.patient_id == patient_id,
            )
            .order_by(CaregiverRelationshipModel.created_at)
        )
        return [caregiver_relationship_to_domain(m) for m in self.session.scalars(stmt).all()]

    def find_by_pair(
        self, caregiver_user_id: UUID, patient_id: UUID
    ) -> CaregiverRelationship | None:
        stmt = select(CaregiverRelationshipModel).where(
            CaregiverRelationshipModel.tenant_id == self.tenant_id,
            CaregiverRelationshipModel.caregiver_user_id == caregiver_user_id,
            CaregiverRelationshipModel.patient_id == patient_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            return None
        return caregiver_relationship_to_domain(model)

    def get_verified_for_patient(
        self, caregiver_user_id: UUID, patient_id: UUID
    ) -> CaregiverRelationship | None:
        stmt = select(CaregiverRelationshipModel).where(
            CaregiverRelationshipModel.tenant_id == self.tenant_id,
            CaregiverRelationshipModel.caregiver_user_id == caregiver_user_id,
            CaregiverRelationshipModel.patient_id == patient_id,
            CaregiverRelationshipModel.status == CaregiverRelationshipStatus.VERIFIED.value,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            return None
        return caregiver_relationship_to_domain(model)