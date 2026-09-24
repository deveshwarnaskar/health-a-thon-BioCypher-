"""GenerateReport command (Gate 10N).

Requests server-authoritative compilation and rendering of a clinical or
patient-facing report (PDF/PNG), storing the resulting artifact in private
object storage (S3) and registering a DocumentReference in the tenant-scoped repository.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GenerateReport:
    patient_id: UUID
    tenant_id: UUID
    requester_user_id: UUID
    report_type: str = "clinical_summary"  # "clinical_summary" or "patient_summary"
    format: str = "pdf"  # "pdf" or "png"
    facility_id: UUID | None = None
    correlation_id: UUID | str | None = None
