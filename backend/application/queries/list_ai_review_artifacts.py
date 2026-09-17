"""ListAIReviewArtifacts query (Gate 10F-B).

Read-side input spell for the clinician pending-review queue. The facility is
derived exclusively from the authenticated care team membership (``assert
clinic facility context``) by the route — never from a client-supplied value.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListAIReviewArtifacts:
    facility_id: UUID
    limit: int = 50