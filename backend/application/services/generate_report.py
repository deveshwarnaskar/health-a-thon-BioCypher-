"""GenerateReportHandler application service (Gate 10N).

Orchestrates the server-authoritative clinical and patient report generation:
1. Authorized validation & patient activity verification
2. Server-side context aggregation with strict information asymmetry
3. Deterministic rendering (PDF / PNG)
4. Private S3 object storage upload with sanitized keys
5. DocumentReference registration in UnitOfWork
6. Domain event emission and transactional commit
"""

from __future__ import annotations

from uuid import UUID

from ..commands.generate_report import GenerateReport
from ..exceptions import InactivePatientError, InvalidReportFormatError
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.storage import IObjectStorage
from ..ports.unit_of_work import UnitOfWork
from ..queries.build_clinical_report_context import BuildClinicalReportContext
from .build_clinical_report_context import BuildClinicalReportContextHandler
from ...domain.entities import DocumentKind, DocumentReference
from ...domain.events import ClinicalReportGenerated
from ...infrastructure.reporting.report_renderer import (
    ClinicalPdfRenderer,
    PatientPdfRenderer,
    PngChartRenderer,
)
from ...infrastructure.storage.s3_storage import build_storage_key


class GenerateReportHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        storage: IObjectStorage,
        events: DomainEventPublisher,
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._events = events
        self._clock = clock
        self._id_gen = id_gen

    def handle(self, cmd: GenerateReport) -> DocumentReference:
        patient = self._uow.patients.get(cmd.patient_id)
        if not getattr(patient, "active", True):
            raise InactivePatientError(f"Patient {cmd.patient_id} is deactivated")

        report_type = cmd.report_type.strip().lower()
        if report_type not in ("clinical_summary", "patient_summary"):
            raise InvalidReportFormatError(f"Unsupported report type: {cmd.report_type}")

        doc_format = cmd.format.strip().lower()
        if doc_format not in ("pdf", "png"):
            raise InvalidReportFormatError(f"Unsupported report format: {cmd.format}")

        # Build authorized, filtered context
        context_handler = BuildClinicalReportContextHandler(self._uow)
        context = context_handler.handle(
            BuildClinicalReportContext(
                patient_id=cmd.patient_id,
                facility_id=cmd.facility_id,
                report_type=report_type,
            )
        )

        # Select deterministic renderer and metadata
        if doc_format == "pdf":
            if report_type == "patient_summary":
                renderer = PatientPdfRenderer()
                doc_kind = DocumentKind.PATIENT_SUMMARY
            else:
                renderer = ClinicalPdfRenderer()
                doc_kind = DocumentKind.CLINICAL_REPORT
            mime_type = "application/pdf"
            ext = "pdf"
        else:
            renderer = PngChartRenderer()
            doc_kind = DocumentKind.CHART_IMAGE
            mime_type = "image/png"
            ext = "png"

        payload_bytes = renderer.render(context)
        doc_id = self._id_gen.new_uuid()

        storage_key = build_storage_key(
            tenant_id=cmd.tenant_id,
            patient_id=cmd.patient_id,
            kind=doc_kind.value,
            document_id=doc_id,
            extension=ext,
        )

        # Store in private object storage
        self._storage.put(storage_key, payload_bytes)

        uh_id_str = context["patient"]["uh_id"]
        now = self._clock.now()
        date_str = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_{uh_id_str}_{date_str}.{ext}"

        doc_ref = DocumentReference(
            id=doc_id,
            tenant_id=cmd.tenant_id,
            patient_id=cmd.patient_id,
            facility_id=cmd.facility_id,
            kind=doc_kind,
            storage_key=storage_key,
            mime_type=mime_type,
            filename=filename,
            file_size_bytes=len(payload_bytes),
            created_by_user_id=cmd.requester_user_id,
            correlation_id=str(cmd.correlation_id) if cmd.correlation_id else None,
            created_at=now,
        )

        self._uow.document_references.add(doc_ref)
        self._events.publish(ClinicalReportGenerated(document_id=doc_id, patient_id=cmd.patient_id))
        self._uow.commit()

        return doc_ref
