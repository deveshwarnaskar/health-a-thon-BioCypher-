"""AIReviewArtifact entity (Gate 03).

Bifurcated AI authority. AI-synthesized workflow artifacts (extracted
evidence, summaries) flow through an explicit clinician review state machine:

    GENERATED -> PENDING_REVIEW -> APPROVED / EDITED / REJECTED
                                  -> ACTION -> AUDIT

This deliberately replaces any generic "AI approved = true" boolean. Patient
confirmation of patient-originated observations is a SEPARATE authority carried
by the observation entities (``PatientConfirmationState``) and is never
collapsed into this review state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from ..exceptions import InvalidStateTransition


class ReviewState(str, Enum):
    GENERATED = "generated"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    ACTIONED = "actioned"
    AUDITED = "audited"


class ReviewAuthority(str, Enum):
    CLINICIAN_REVIEW = "clinician_review"
    PATIENT_CONFIRMATION = "patient_confirmation"


_ALLOWED_TRANSITIONS = {
    ReviewState.GENERATED: {ReviewState.PENDING_REVIEW},
    ReviewState.PENDING_REVIEW: {ReviewState.APPROVED, ReviewState.EDITED, ReviewState.REJECTED},
    ReviewState.APPROVED: {ReviewState.ACTIONED},
    ReviewState.EDITED: {ReviewState.ACTIONED},
    ReviewState.REJECTED: set(),
    ReviewState.ACTIONED: {ReviewState.AUDITED},
    ReviewState.AUDITED: set(),
}


@dataclass
class AIReviewArtifact:
    id: UUID = field(default_factory=uuid4)
    patient_id: UUID = field(default_factory=uuid4)
    artifact_kind: str = "extracted_observation"
    authority: ReviewAuthority = ReviewAuthority.CLINICIAN_REVIEW
    state: ReviewState = ReviewState.GENERATED
    generated_by: str = "ai"
    summary: str = ""
    reviewed_by_user_id: UUID | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def _transition(self, target: ReviewState) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(self.state)
        if allowed is None or target not in allowed:
            raise InvalidStateTransition(
                f"AI artifact cannot move {self.state.value} -> {target.value}"
            )
        self.state = target

    def submit_for_review(self) -> None:
        self._transition(ReviewState.PENDING_REVIEW)

    def approve(self, reviewer: UUID) -> None:
        self._transition(ReviewState.APPROVED)
        self.reviewed_by_user_id = reviewer

    def edit(self, reviewer: UUID, edited_summary: str) -> None:
        self._transition(ReviewState.EDITED)
        self.summary = edited_summary
        self.reviewed_by_user_id = reviewer

    def reject(self, reviewer: UUID) -> None:
        self._transition(ReviewState.REJECTED)
        self.reviewed_by_user_id = reviewer

    def action(self) -> None:
        self._transition(ReviewState.ACTIONED)

    def audit(self) -> None:
        self._transition(ReviewState.AUDITED)