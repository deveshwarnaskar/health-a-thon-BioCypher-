"""SqlAlchemyClinicalObservationRepository.

Tenant-scoped repository implementation for general clinical observations
(labs, vitals, screenings, symptoms, document extractions).
"""

from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities.clinical_observation import ClinicalObservation
from ..mappings.mappers import (
    clinical_observation_to_domain,
    clinical_observation_to_model,
)
from ..models.observation_models import ClinicalObservationModel


class SqlAlchemyClinicalObservationRepository:
    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyClinicalObservationRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, obs: ClinicalObservation) -> None:
        model = clinical_observation_to_model(obs, self.tenant_id)
        self.session.add(model)

    def get(self, obs_id: UUID) -> Optional[ClinicalObservation]:
        stmt = select(ClinicalObservationModel).where(
            ClinicalObservationModel.id == obs_id,
            ClinicalObservationModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        return clinical_observation_to_domain(model) if model else None

    def list_for_patient(
        self,
        patient_id: UUID,
        observation_type: Optional[str] = None,
        code: Optional[str] = None,
    ) -> list[ClinicalObservation]:
        stmt = select(ClinicalObservationModel).where(
            ClinicalObservationModel.tenant_id == self.tenant_id,
            ClinicalObservationModel.patient_id == patient_id,
        )
        if observation_type:
            stmt = stmt.where(ClinicalObservationModel.observation_type == observation_type)
        if code:
            stmt = stmt.where(ClinicalObservationModel.code == code)
        stmt = stmt.order_by(ClinicalObservationModel.observed_at.desc())
        models = self.session.scalars(stmt).all()
        return [clinical_observation_to_domain(m) for m in models]

    def list_for_document(self, document_id: UUID) -> list[ClinicalObservation]:
        stmt = select(ClinicalObservationModel).where(
            ClinicalObservationModel.tenant_id == self.tenant_id,
            ClinicalObservationModel.document_id == document_id,
        ).order_by(ClinicalObservationModel.observed_at.desc())
        models = self.session.scalars(stmt).all()
        return [clinical_observation_to_domain(m) for m in models]

