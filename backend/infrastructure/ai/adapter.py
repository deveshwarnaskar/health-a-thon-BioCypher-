"""Provider-neutral AI adapter (Gate 05 + Gate 10M).

Implements the application AIArtifactGenerator port and delegates to an underlying AIProvider.
Produces unapproved drafts only. Never performs autonomous action or approval.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from backend.application.ports.ai import (
    AIArtifactGenerator,
    AIProvider,
    AIProviderResult,
    AITaskDefinition,
    AITaskType,
    ArtifactDraft,
    DEFAULT_SYSTEM_CONSTRAINTS,
    EvidencePackage,
)
from .deterministic_demo_provider import DeterministicDemoProvider


class ProviderNeutralAIAdapter:
    """Provider-neutral AI adapter delegating to an underlying AIProvider."""

    def __init__(
        self,
        provider: AIProvider | None = None,
        artifact_kind: str = "extracted_observation",
        model_name: str = "deterministic-demo-v1",
    ) -> None:
        self.provider: AIProvider = provider or DeterministicDemoProvider(model_name=model_name)
        self.artifact_kind = artifact_kind
        self.model_name = model_name

    def generate(self, context: str, patient_id: UUID) -> ArtifactDraft:
        """Legacy generation method matching AIArtifactGenerator port."""
        trimmed_context = context[:80].strip() if context else "empty"
        summary = f"Synthesized draft from input: {trimmed_context}"
        return ArtifactDraft(
            artifact_kind=self.artifact_kind,
            summary=summary,
            context_id=uuid4(),
        )

    def generate_with_provider(
        self, task: AITaskDefinition, evidence: EvidencePackage
    ) -> AIProviderResult:
        """Generate draft through underlying provider."""
        return self.provider.generate(task, evidence)
