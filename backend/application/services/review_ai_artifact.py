"""ReviewAIArtifact use case (Gate 04).

Licensed clinician review of a pending AI artifact. The reviewer is resolved
from the authoritative ``CareTeamMember`` record and must hold a licensed
clinical role (doctor / nurse / dietitian). The artifact state machine is
domain-governed: illegal transitions raise ``InvalidStateTransition`` and the
transaction rolls back.
"""

from ..commands import ReviewAIArtifact, ReviewDecision
from ..dtos.results import AIArtifactReviewedResult
from ..exceptions import ReviewerNotAuthorized
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import CareTeamRole
from ...domain.events import AIArtifactReviewed
from ._transaction import in_transaction

_LICENSED_ROLES = {CareTeamRole.DOCTOR, CareTeamRole.NURSE, CareTeamRole.DIETITIAN}


class ReviewAIArtifactHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        events: DomainEventPublisher,
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow = uow
        self._events = events
        self._clock = clock
        self._id_gen = id_gen

    def handle(self, cmd: ReviewAIArtifact) -> AIArtifactReviewedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: ReviewAIArtifact) -> AIArtifactReviewedResult:
        artifact = self._uow.ai_artifacts.get(cmd.artifact_id)
        member = self._uow.care_team_members.get(cmd.reviewer_user_id)
        if member.role not in _LICENSED_ROLES:
            raise ReviewerNotAuthorized(
                f"role {member.role.value} cannot review AI artifacts; "
                "only licensed clinicians may review"
            )
        now = self._clock.now()
        if cmd.decision == ReviewDecision.APPROVE:
            artifact.approve(cmd.reviewer_user_id, at=now)
        elif cmd.decision == ReviewDecision.EDIT:
            if cmd.edited_summary is None:
                raise ValueError("edited_summary is required for the EDIT decision")
            artifact.edit(cmd.reviewer_user_id, cmd.edited_summary, at=now)
        elif cmd.decision == ReviewDecision.REJECT:
            artifact.reject(cmd.reviewer_user_id, at=now)
        self._uow.ai_artifacts.save(artifact)
        self._events.publish(
            AIArtifactReviewed(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=artifact.patient_id,
                correlation_id=cmd.correlation_id,
                artifact_id=artifact.id,
                review_state=artifact.state.value,
            )
        )
        return AIArtifactReviewedResult(
            artifact_id=artifact.id,
            state=artifact.state.value,
            reviewed_by_user_id=cmd.reviewer_user_id,
        )