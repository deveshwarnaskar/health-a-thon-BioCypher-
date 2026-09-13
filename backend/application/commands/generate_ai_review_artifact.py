"""GenerateAIReviewArtifact command (Gate 04).

Delegates to the provider-neutral AI port and records the resulting DRAFT as a
domain ``AIReviewArtifact``. The artifact is transitioned ONLY as far as
"pending review" (never approved/actioned) before any clinician has reviewed it.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GenerateAIReviewArtifact:
    patient_id: UUID
    artifact_kind: str
    context: str
    correlation_id: UUID | None = None