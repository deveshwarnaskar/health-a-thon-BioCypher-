"""SqlAlchemyPatientRepository (Gate 05).

Concrete infrastructure implementation of PatientRepository port.
Enforces multi-tenant scoping and reconstructs pure domain Patient entities.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import Patient
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import patient_to_domain, patient_to_model
from ..models.patient_models import PatientModel


class SqlAlchemyPatientRepository:
    """SQLAlchemy-backed repository for Patient aggregates."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyPatientRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, patient: Patient) -> None:
        model = patient_to_model(patient, self.tenant_id)
        self.session.add(model)

    def get(self, patient_id: UUID) -> Patient:
        stmt = select(PatientModel).where(
            PatientModel.id == patient_id,
            PatientModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"patient {patient_id} not found")
        return patient_to_domain(model)

    def save(self, patient: Patient) -> None:
        stmt = select(PatientModel).where(
            PatientModel.id == patient.id,
            PatientModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"patient {patient.id} not found")
        model.name = patient.name
        model.uh_id = patient.uh_id.value
        model.phone = patient.phone.value if patient.phone else None
        model.facility_id = patient.facility_id
        model.active = patient.active

    def list(self) -> list[Patient]:
        stmt = (
            select(PatientModel)
            .where(PatientModel.tenant_id == self.tenant_id)
            .order_by(PatientModel.created_at)
        )
        return [patient_to_domain(m) for m in self.session.scalars(stmt).all()]
