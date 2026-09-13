"""GenerateAIReviewArtifact use case (Gate 04).

Delegates to the provider-neutral AI port and records the resulting DRAFT as a
domain ``AIReviewArtifact``. The artifact is transitioned ONLY as far as
``pending_review`` (never approved/actioned) before any clinician has reviewed it.

AI must never directly approve or action an artifact.
"""

from ..commands import GenerateAIReviewArtifact
from ..dtos.results import AIArtifactGeneratedResult
from ..ports.ai import AIArtifactGenerator
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ...domain.entities import AIReviewArtifact, ReviewAuthority, ReviewState
from ...domain.events import AIArtifactGenerated
from ._transaction import in_transaction


class GenerateAIReviewArtifactHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        events: DomainEventPublisher,
        ai: AIArtifactGenerator,
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow = uow
        self._events = events
        self._ai = ai
        self._clock = clock
        self._id_gen = id_gen

    def handle(self, cmd: GenerateAIReviewArtifact) -> AIArtifactGeneratedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: GenerateAIReviewArtifact) -> AIArtifactGeneratedResult:
        draft = self._ai.generate(cmd.context, cmd.patient_id)
        artifact = AIReviewArtifact(
            id=self._id_gen.new_uuid(),
            patient_id=cmd.patient_id,
            artifact_kind=draft.artifact_kind,
            authority=ReviewAuthority.CLINICIAN_REVIEW,
            state=ReviewState.GENERATED,
            generated_by="ai",
            summary=draft.summary,
            created_at=self._clock.now(),
        )
        artifact.submit_for_review()
        self._uow.ai_artifacts.add(artifact)
        self._events.publish(
            AIArtifactGenerated(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=cmd.patient_id,
                correlation_id=cmd.correlation_id,
                artifact_id=artifact.id,
            )
        )
        return AIArtifactGeneratedResult(
            artifact_id=artifact.id,
            patient_id=cmd.patient_id,
            state=artifact.state.value,
            summary=artifact.summary,
        )