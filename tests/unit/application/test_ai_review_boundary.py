"""Gate 04 — AI review boundary.

The application preserves the frozen AI workflow:

    GENERATED -> PENDING_REVIEW -> APPROVE / EDIT / REJECT -> ACTION -> AUDIT

AI generation produces a DRAFT and never transitions to an approved/actionable
state. Only the clinician review use case advances the artifact.
"""

import pytest

from backend.application.commands import (
    GenerateAIReviewArtifact,
    ReviewAIArtifact,
    ReviewDecision,
)
from backend.application.exceptions import ReviewerNotAuthorized
from backend.domain.entities import ReviewAuthority, ReviewState
from backend.domain.events import AIArtifactGenerated, AIArtifactReviewed
from backend.domain.exceptions import InvalidStateTransition


def test_generated_artifact_never_leaves_review_pipeline_approved(world):
    app, ai = world["app"], world["ai"]

    result = app.generate_ai_artifact.handle(
        GenerateAIReviewArtifact(
            patient_id=world["patient_id"],
            artifact_kind="glucose_summary",
            context="some evidence",
        )
    )

    assert result.state == "pending_review"
    stored = world["uow"].ai_artifacts.get(result.artifact_id)
    assert stored.state is ReviewState.PENDING_REVIEW
    assert stored.authority is ReviewAuthority.CLINICIAN_REVIEW
    # the AI port produces drafts without approval semantics
    draft = ai.generate("x", world["patient_id"])
    assert not hasattr(draft, "state")


def test_ai_port_draft_is_not_an_approval(world):
    draft = world["ai"].generate("context", world["patient_id"])
    assert draft.summary == world["ai"].summary
    assert not hasattr(draft, "approved")


def test_generate_publishes_generated_not_reviewed(world):
    world["app"].generate_ai_artifact.handle(
        GenerateAIReviewArtifact(
            patient_id=world["patient_id"],
            artifact_kind="summary",
            context="data",
        )
    )
    types = {type(e) for e in world["events"].published}
    assert AIArtifactGenerated in types
    assert AIArtifactReviewed not in types


def test_review_requires_pending_state_approve_then_action(world):
    app = world["app"]
    generated = app.generate_ai_artifact.handle(
        GenerateAIReviewArtifact(
            patient_id=world["patient_id"], artifact_kind="summary", context="data"
        )
    )

    # approving from pending is the licensed clinician path
    reviewed = app.review_ai_artifact.handle(
        ReviewAIArtifact(
            artifact_id=generated.artifact_id,
            reviewer_user_id=world["doctor_user_id"],
            decision=ReviewDecision.APPROVE,
        )
    )
    assert reviewed.state == "approved"

    # the same artifact cannot be reviewed twice (domain state machine)
    with pytest.raises(InvalidStateTransition):
        app.review_ai_artifact.handle(
            ReviewAIArtifact(
                artifact_id=generated.artifact_id,
                reviewer_user_id=world["doctor_user_id"],
                decision=ReviewDecision.REJECT,
            )
        )


def test_ai_cannot_directly_approve_generated_artifact(world):
    """No application path moves a NEW artifact to approved without review."""
    app = world["app"]
    generated = app.generate_ai_artifact.handle(
        GenerateAIReviewArtifact(
            patient_id=world["patient_id"],
            artifact_kind="summary",
            context="data",
        )
    )
    assert world["uow"].ai_artifacts.get(generated.artifact_id).state is ReviewState.PENDING_REVIEW

    # a bare GENERATED artifact cannot be approved by the domain either
    from backend.domain.entities import AIReviewArtifact

    artifact = AIReviewArtifact(patient_id=world["patient_id"])
    with pytest.raises(InvalidStateTransition):
        artifact.approve(world["doctor_user_id"])
    with pytest.raises(InvalidStateTransition):
        artifact.action()


def test_reject_publishes_reviewed_state(world):
    app = world["app"]
    generated = app.generate_ai_artifact.handle(
        GenerateAIReviewArtifact(
            patient_id=world["patient_id"], artifact_kind="summary", context="data"
        )
    )
    reviewed = app.review_ai_artifact.handle(
        ReviewAIArtifact(
            artifact_id=generated.artifact_id,
            reviewer_user_id=world["nurse_user_id"],
            decision=ReviewDecision.REJECT,
        )
    )
    assert reviewed.state == "rejected"
    event = world["events"].published[-1]
    assert isinstance(event, AIArtifactReviewed)
    assert event.review_state == "rejected"


def test_edit_requires_edited_summary(world):
    app = world["app"]
    generated = app.generate_ai_artifact.handle(
        GenerateAIReviewArtifact(
            patient_id=world["patient_id"], artifact_kind="summary", context="data"
        )
    )
    edited = app.review_ai_artifact.handle(
        ReviewAIArtifact(
            artifact_id=generated.artifact_id,
            reviewer_user_id=world["doctor_user_id"],
            decision=ReviewDecision.EDIT,
            edited_summary="corrected summary here",
        )
    )
    assert edited.state == "edited"
    stored = world["uow"].ai_artifacts.get(generated.artifact_id)
    assert stored.summary == "corrected summary here"
    assert stored.reviewed_by_user_id == world["doctor_user_id"]


def test_non_clinician_cannot_review(world):
    app = world["app"]
    generated = app.generate_ai_artifact.handle(
        GenerateAIReviewArtifact(
            patient_id=world["patient_id"], artifact_kind="summary", context="data"
        )
    )
    with pytest.raises(ReviewerNotAuthorized):
        app.review_ai_artifact.handle(
            ReviewAIArtifact(
                artifact_id=generated.artifact_id,
                reviewer_user_id=world["coordinator_user_id"],
                decision=ReviewDecision.APPROVE,
            )
        )

    stored = world["uow"].ai_artifacts.get(generated.artifact_id)
    assert stored.state is ReviewState.PENDING_REVIEW
    assert stored.reviewed_by_user_id is None