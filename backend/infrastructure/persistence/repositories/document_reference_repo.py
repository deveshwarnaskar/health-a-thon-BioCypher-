"""SqlAlchemyDocumentReferenceRepository (Gate 10N).

Concrete infrastructure implementation of DocumentReferenceRepository port.
Enforces multi-tenant scoping and persists document reference records.
"""

from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities import DocumentKind, DocumentReference
from backend.domain.exceptions import EntityNotFound
from ..mappings.mappers import document_reference_to_domain, document_reference_to_model
from ..models.document_models import DocumentReferenceModel


class SqlAlchemyDocumentReferenceRepository:
    """SQLAlchemy-backed repository for DocumentReference entities."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        if tenant_id is None:
            raise ValueError("tenant_id is required for SqlAlchemyDocumentReferenceRepository")
        self.session = session
        self.tenant_id = tenant_id

    def add(self, doc_ref: DocumentReference) -> None:
        model = document_reference_to_model(doc_ref, self.tenant_id)
        self.session.add(model)

    def get(self, document_id: UUID) -> DocumentReference:
        stmt = select(DocumentReferenceModel).where(
            DocumentReferenceModel.id == document_id,
            DocumentReferenceModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is None:
            raise EntityNotFound(f"document reference {document_id} not found")
        return document_reference_to_domain(model)

    def list_for_patient(
        self, patient_id: UUID, kind: DocumentKind | None = None
    ) -> list[DocumentReference]:
        stmt = select(DocumentReferenceModel).where(
            DocumentReferenceModel.patient_id == patient_id,
            DocumentReferenceModel.tenant_id == self.tenant_id,
        )
        if kind is not None:
            kind_str = kind.value if hasattr(kind, "value") else str(kind)
            stmt = stmt.where(DocumentReferenceModel.kind == kind_str)
        stmt = stmt.order_by(DocumentReferenceModel.created_at.desc())
        models = self.session.scalars(stmt).all()
        return [document_reference_to_domain(m) for m in models]

    def list_for_tenant(
        self, limit: int = 50, offset: int = 0
    ) -> list[DocumentReference]:
        stmt = (
            select(DocumentReferenceModel)
            .where(DocumentReferenceModel.tenant_id == self.tenant_id)
            .order_by(DocumentReferenceModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = self.session.scalars(stmt).all()
        return [document_reference_to_domain(m) for m in models]

    def delete(self, document_id: UUID) -> None:
        stmt = select(DocumentReferenceModel).where(
            DocumentReferenceModel.id == document_id,
            DocumentReferenceModel.tenant_id == self.tenant_id,
        )
        model = self.session.scalars(stmt).first()
        if model is not None:
            self.session.delete(model)
