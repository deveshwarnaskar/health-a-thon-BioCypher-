"""GenerateAIReviewArtifact use case (Gate 04 + Gate 10M).

Delegates to an authorized AIProvider via EvidenceBuilder and records the resulting
DRAFT as a domain ``AIReviewArtifact``. The artifact is transitioned ONLY as far as
``pending_review`` (never approved/actioned) before any licensed clinician has reviewed it.

AI must never directly approve, action, prescribe, or mutate medical records.
"""

from __future__ import annotations

from uuid import UUID

from ..commands import GenerateAIReviewArtifact
from ..dtos.results import AIArtifactGeneratedResult
from ..exceptions import AIGenerationFailed
from ..ports.ai import (
    AIArtifactGenerator,
    AIProvider,
    AIProviderResult,
    AITaskDefinition,
    AITaskType,
    DEFAULT_SYSTEM_CONSTRAINTS,
    EvidencePackage,
)
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from .evidence_builder import EvidenceBuilder
from ...domain.entities import AIReviewArtifact, ReviewAuthority, ReviewState
from ...domain.events import AIArtifactGenerated
from ._transaction import in_transaction


class GenerateAIReviewArtifactHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        events: DomainEventPublisher,
        ai: AIArtifactGenerator | AIProvider | None = None,
        clock: Clock | None = None,
        id_gen: IdGenerator | None = None,
        evidence_builder: EvidenceBuilder | None = None,
        provider: AIProvider | None = None,
    ) -> None:
        self._uow = uow
        self._events = events
        self._ai = ai
        self._clock = clock
        self._id_gen = id_gen
        self._evidence_builder = evidence_builder or EvidenceBuilder()
        self._provider = provider

    def handle(self, cmd: GenerateAIReviewArtifact) -> AIArtifactGeneratedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: GenerateAIReviewArtifact) -> AIArtifactGeneratedResult:
        tenant_id = (
            cmd.tenant_id
            or getattr(self._uow, "tenant_id", None)
            or UUID("00000000-0000-0000-0000-000000000000")
        )

        evidence_hash: str | None = None
        model_name: str | None = None
        summary: str = ""

        if self._provider is not None:
            # Build server-authorized evidence
            evidence = self._evidence_builder.build(
                patient_id=cmd.patient_id,
                tenant_id=tenant_id,
                uow=self._uow,
                user_notes=cmd.context,
            )
            evidence_hash = evidence.evidence_hash

            # Map task type safely
            task_type_val = AITaskType.CLINICAL_SUMMARY
            try:
                task_type_val = AITaskType(cmd.task_type)
            except ValueError:
                task_type_val = AITaskType.CLINICAL_SUMMARY

            task = AITaskDefinition(
                task_type=task_type_val,
                system_constraints=DEFAULT_SYSTEM_CONSTRAINTS,
                patient_id=cmd.patient_id,
                tenant_id=tenant_id,
                correlation_id=str(cmd.correlation_id) if cmd.correlation_id else None,
            )

            result: AIProviderResult = self._provider.generate(task, evidence)
            if not result.success:
                raise AIGenerationFailed(
                    error_code=result.error_code,
                    retryable=result.retryable,
                    message=f"AI generation failed: {result.error_code}",
                )

            summary = result.summary
            model_name = result.model
        elif self._ai is not None:
            # Legacy AIArtifactGenerator path
            draft = self._ai.generate(cmd.context, cmd.patient_id)
            summary = draft.summary
            model_name = getattr(self._ai, "model_name", "ai")
        else:
            raise AIGenerationFailed("NO_PROVIDER_CONFIGURED", retryable=False)

        artifact_id = self._id_gen.new_uuid() if self._id_gen else UUID()
        now = self._clock.now() if self._clock else None

        artifact = AIReviewArtifact(
            id=artifact_id,
            patient_id=cmd.patient_id,
            tenant_id=tenant_id,
            artifact_kind=cmd.artifact_kind,
            authority=ReviewAuthority.CLINICIAN_REVIEW,
            state=ReviewState.GENERATED,
            generated_by=f"ai:{model_name}" if model_name else "ai",
            summary=summary,
            model_name=model_name,
            evidence_hash=evidence_hash,
            correlation_id=str(cmd.correlation_id) if cmd.correlation_id else None,
            created_at=now,
        )

        # Transition strictly to PENDING_REVIEW (never APPROVED!)
        artifact.submit_for_review()

        self._uow.ai_artifacts.add(artifact)

        if self._events:
            event_id = self._id_gen.new_uuid() if self._id_gen else UUID()
            self._events.publish(
                AIArtifactGenerated(
                    event_id=event_id,
                    occurred_at=now,
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