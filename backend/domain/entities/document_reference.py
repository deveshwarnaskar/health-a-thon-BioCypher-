"""DocumentReference entity (Gate 03).

Pointer to a stored artifact (report PDF, chart image, photo). Holds an opaque
``storage_key`` only — no filesystem or S3 SDK knowledge lives in the domain.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class DocumentKind(str, Enum):
    CLINICAL_REPORT = "clinical_report"
    CHART_IMAGE = "chart_image"
    MEAL_PHOTO = "meal_photo"
    AI_ARTIFACT = "ai_artifact"


@dataclass(frozen=True)
class DocumentReference:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    kind: DocumentKind = DocumentKind.CLINICAL_REPORT
    storage_key: str = ""
    mime_type: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)