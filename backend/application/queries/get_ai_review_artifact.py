"""GetAIReviewArtifact query (Gate 10F-B).

Read-side input spell for one AI review artifact. The facility is derived from
the authenticated care team membership; the handler only returns artifacts
whose patient belongs to that facility and is active (deactivated patients
never surface through clinician reads).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetAIReviewArtifact:
    artifact_id: UUID
    facility_id: UUID