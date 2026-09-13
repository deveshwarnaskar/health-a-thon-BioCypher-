"""Gate 03 — Bifurcated AI authority and review-state machine."""

from uuid import uuid4

import pytest

from backend.domain.entities import (
    AIReviewArtifact,
    ReviewAuthority,
    ReviewState,
)
from backend.domain.exceptions import InvalidStateTransition
from backend.domain.value_objects import PatientConfirmationState


def _artifact() -> AIReviewArtifact:
    return AIReviewArtifact(patient_id=uuid4())


def test_generated_to_pending_review_valid():
    a = _artifact()
    a.submit_for_review()
    assert a.state is ReviewState.PENDING_REVIEW


def test_full_approval_and_audit_path():
    a = _artifact()
    a.submit_for_review()
    a.approve(reviewer=uuid4())
    assert a.state is ReviewState.APPROVED
    a.action()
    assert a.state is ReviewState.ACTIONED
    a.audit()
    assert a.state is ReviewState.AUDITED


def test_edit_path_records_clinician():
    a = _artifact()
    a.submit_for_review()
    reviewer = uuid4()
    a.edit(reviewer=reviewer, edited_summary="range 180-190 suspected")
    assert a.state is ReviewState.EDITED
    assert a.reviewed_by_user_id == reviewer
    assert a.summary == "range 180-190 suspected"


def test_reject_path_terminal():
    a = _artifact()
    a.submit_for_review()
    a.reject(reviewer=uuid4())
    assert a.state is ReviewState.REJECTED


def test_generated_to_approved_invalid():
    a = _artifact()
    with pytest.raises(InvalidStateTransition):
        a.approve(reviewer=uuid4())


def test_double_submit_invalid():
    a = _artifact()
    a.submit_for_review()
    with pytest.raises(InvalidStateTransition):
        a.submit_for_review()


def test_rejected_cannot_be_approved():
    a = _artifact()
    a.submit_for_review()
    a.reject(reviewer=uuid4())
    with pytest.raises(InvalidStateTransition):
        a.approve(reviewer=uuid4())


def test_actioned_cannot_revert_to_generated():
    a = _artifact()
    a.submit_for_review()
    a.approve(reviewer=uuid4())
    a.action()
    with pytest.raises(InvalidStateTransition):
        a._transition(ReviewState.GENERATED)


def test_patient_confirmation_not_collapsed_with_clinician_review():
    artifact = _artifact()
    assert artifact.state is ReviewState.GENERATED
    assert artifact.authority is ReviewAuthority.CLINICIAN_REVIEW
    assert not hasattr(artifact, "confirmed")
    assert ReviewAuthority.PATIENT_CONFIRMATION.value != PatientConfirmationState.CONFIRMED.value