"""ReviewAIArtifact command (Gate 04).

Human (licensed clinician) review of a pending AI artifact:

- decision ``approve`` -> domain ``approve``
- decision ``edit``   -> domain ``edit`` (carries edited summary)
- decision ``reject`` -> domain ``reject``

The reviewer is resolved from the authoritative ``CareTeamMember`` record and
must hold a licensed clinical role. The artifact must already be
``pending_review``; the domain state machine rejects illegal transitions.
"""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


@dataclass(frozen=True)
class ReviewAIArtifact:
    artifact_id: UUID
    reviewer_user_id: UUID
    decision: ReviewDecision
    edited_summary: str | None = None
    correlation_id: UUID | None = None