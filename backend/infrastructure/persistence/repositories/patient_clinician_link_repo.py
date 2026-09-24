"""SqlAlchemyPatientClinicianLinkRepository (Gate 13).

Concrete infrastructure implementation of the PatientClinicianLinkRepository
port. All queries are tenant-scoped. Reconstructs pure domain entities.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import PatientClinicianLink
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import (
    patient_clinician_link_to_domain,
    patient_clinician_link_to_model,
)
from ..models.identity_models import PatientClinicianLinkModel


class SqlAlchemyPatientClinicianLinkRepository:
    """SQLAlchemy-backed repository for PatientClinicianLink entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyPatientClinicianLinkRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, link: PatientClinicianLink) -> None:
        model = patient_clinician_link_to_model(link, self.tenant_id)
        self.session.add(model)

    def get(self, link_id: UUID) -> PatientClinicianLink:
        stmt = select(PatientClinicianLinkModel).where(
            PatientClinicianLinkModel.id == link_id,
            PatientClinicianLinkModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"patient clinician link {link_id} not found")
        return patient_clinician_link_to_domain(model)

    def add(self, link: PatientClinicianLink) -> None:
        self.session.add(patient_clinician_link_to_model(link, self.tenant_id))

    def save(self, link: PatientClinicianLink) -> None:
        stmt = select(PatientClinicianLinkModel).where(
            PatientClinicianLinkModel.id == link.id,
            PatientClinicianLinkModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"patient clinician link {link.id} not found")
        model.facility_id = link.facility_id
        model.clinician_name = link.clinician_name
        model.active = link.active
        model.updated_at = link.updated_at

    def find_by_active_pair(
        self, patient_id: UUID, clinician_user_id: UUID
    ) -> PatientClinicianLink | None:
        stmt = select(PatientClinicianLinkModel).where(
            PatientClinicianLinkModel.tenant_id == self.tenant_id,
            PatientClinicianLinkModel.patient_id == patient_id,
            PatientClinicianLinkModel.clinician_user_id == clinician_user_id,
            PatientClinicianLinkModel.active.is_(True),
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            return None
        return patient_clinician_link_to_domain(model)

    def list_for_patient(self, patient_id: UUID) -> list[PatientClinicianLink]:
        stmt = (
            select(PatientClinicianLinkModel)
            .where(
                PatientClinicianLinkModel.tenant_id == self.tenant_id,
                PatientClinicianLinkModel.patient_id == patient_id,
                PatientClinicianLinkModel.active.is_(True),
            )
            .order_by(PatientClinicianLinkModel.created_at)
        )
        return [patient_clinician_link_to_domain(m) for m in self.session.scalars(stmt).all()]