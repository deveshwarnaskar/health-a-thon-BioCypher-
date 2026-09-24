"""UploadDocument command (Gate 10N).

Uploads an external clinical document, chart image, or meal photo to private
storage and records its DocumentReference.
"""

from dataclasses import dataclass
from uuid import UUID

from backend.domain.entities.document_reference import DocumentKind


@dataclass(frozen=True)
class UploadDocument:
    patient_id: UUID
    tenant_id: UUID
    uploader_user_id: UUID
    filename: str
    mime_type: str
    payload: bytes
    facility_id: UUID | None = None
    kind: DocumentKind = DocumentKind.CHART_IMAGE
    correlation_id: str | None = None
