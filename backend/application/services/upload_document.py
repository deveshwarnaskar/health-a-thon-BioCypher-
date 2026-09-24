"""UploadDocumentHandler application service (Gate 10N).

Handles authorized external document uploads to private S3 storage.
Validates MIME types, enforcing size limits and server-side sanitized paths.
"""

from __future__ import annotations

from ..commands.upload_document import UploadDocument
from ..exceptions import InactivePatientError
from ..ports.clock import Clock
from ..ports.id_generation import IdGenerator
from ..ports.storage import IObjectStorage
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import DocumentKind, DocumentReference
from ...infrastructure.storage.s3_storage import build_storage_key

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class UploadDocumentHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        storage: IObjectStorage,
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._clock = clock
        self._id_gen = id_gen

    def handle(self, cmd: UploadDocument) -> DocumentReference:
        patient = self._uow.patients.get(cmd.patient_id)
        if not getattr(patient, "active", True):
            raise InactivePatientError(f"Patient {cmd.patient_id} is deactivated")

        clean_mime = cmd.mime_type.strip().lower()
        if clean_mime not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported document MIME type: {cmd.mime_type}")

        if len(cmd.payload) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size {len(cmd.payload)} exceeds maximum allowed limit ({MAX_FILE_SIZE_BYTES} bytes)")

        ext = ALLOWED_MIME_TYPES[clean_mime]
        doc_id = self._id_gen.new_uuid()

        storage_key = build_storage_key(
            tenant_id=cmd.tenant_id,
            patient_id=cmd.patient_id,
            kind=cmd.kind.value,
            document_id=doc_id,
            extension=ext,
        )

        self._storage.put(storage_key, cmd.payload)

        doc_ref = DocumentReference(
            id=doc_id,
            tenant_id=cmd.tenant_id,
            patient_id=cmd.patient_id,
            facility_id=cmd.facility_id,
            kind=cmd.kind,
            storage_key=storage_key,
            mime_type=clean_mime,
            filename=cmd.filename or f"upload_{doc_id}.{ext}",
            file_size_bytes=len(cmd.payload),
            created_by_user_id=cmd.uploader_user_id,
            correlation_id=str(cmd.correlation_id) if cmd.correlation_id else None,
            created_at=self._clock.now(),
        )

        self._uow.document_references.add(doc_ref)
        self._uow.commit()

        return doc_ref
