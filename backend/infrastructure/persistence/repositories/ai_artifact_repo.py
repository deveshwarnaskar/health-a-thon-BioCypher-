"""SqlAlchemyAIReviewArtifactRepository (Gate 05).

Concrete infrastructure implementation of AIReviewArtifactRepository port.
Enforces multi-tenant scoping and persists AI artifact review state transitions.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import AIReviewArtifact
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import ai_artifact_to_domain, ai_artifact_to_model
from ..models.ai_models import AIReviewArtifactModel


class SqlAlchemyAIReviewArtifactRepository:
    """SQLAlchemy-backed repository for AIReviewArtifact entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyAIReviewArtifactRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, artifact: AIReviewArtifact) -> None:
        model = ai_artifact_to_model(artifact, self.tenant_id)
        self.session.add(model)

    def get(self, artifact_id: UUID) -> AIReviewArtifact:
        stmt = select(AIReviewArtifactModel).where(
            AIReviewArtifactModel.id == artifact_id,
            AIReviewArtifactModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"ai_artifact {artifact_id} not found")
        return ai_artifact_to_domain(model)

    def save(self, artifact: AIReviewArtifact) -> None:
        stmt = select(AIReviewArtifactModel).where(
            AIReviewArtifactModel.id == artifact.id,
            AIReviewArtifactModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"ai_artifact {artifact.id} not found")
        model.state = artifact.state.value
        model.summary = artifact.summary
        model.reviewed_by_user_id = artifact.reviewed_by_user_id

    def list_for_patient(self, patient_id: UUID) -> list[AIReviewArtifact]:
        stmt = (
            select(AIReviewArtifactModel)
            .where(
                AIReviewArtifactModel.patient_id == patient_id,
                AIReviewArtifactModel.tenant_id == self.tenant_id,
            )
            .order_by(AIReviewArtifactModel.created_at)
        )
        return [ai_artifact_to_domain(m) for m in self.session.scalars(stmt).all()]
