"""DocumentReference entity (Gate 03).

Pointer to a stored artifact (report PDF, chart image, photo). Holds an opaque
``storage_key`` only — no filesystem or S3 SDK knowledge lives in the domain.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


class DocumentKind(str, Enum):
    CLINICAL_REPORT = "clinical_report"
    PATIENT_SUMMARY = "patient_summary"
    CHART_IMAGE = "chart_image"
    MEAL_PHOTO = "meal_photo"
    AI_ARTIFACT = "ai_artifact"


@dataclass(frozen=True)
class DocumentReference:
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    facility_id: UUID | None = None
    kind: DocumentKind = DocumentKind.CLINICAL_REPORT
    storage_key: str = ""
    mime_type: str = ""
    filename: str = ""
    file_size_bytes: int = 0
    created_by_user_id: UUID | None = None
    correlation_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))