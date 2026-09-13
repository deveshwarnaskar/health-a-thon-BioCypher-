"""Provider-neutral AI adapter (Gate 05).

Implements the application AIArtifactGenerator port.
Produces unapproved drafts only. Never performs autonomous action or approval.
No live external network calls are performed.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from backend.application.ports.ai import ArtifactDraft


class ProviderNeutralAIAdapter:
    """Provider-neutral AI generator returning unapproved ArtifactDrafts."""

    def __init__(
        self,
        artifact_kind: str = "extracted_observation",
        model_name: str = "gemini-1.5-pro",
    ) -> None:
        self.artifact_kind = artifact_kind
        self.model_name = model_name

    def generate(self, context: str, patient_id: UUID) -> ArtifactDraft:
        """Generate an unapproved draft artifact from raw context.
        
        CRITICAL: Output is strictly a draft (ReviewState.GENERATED -> PENDING_REVIEW).
        AI can never approve, action, or prescribe.
        """
        trimmed_context = context[:80].strip() if context else "empty"
        summary = f"Synthesized draft from input: {trimmed_context}"
        return ArtifactDraft(
            artifact_kind=self.artifact_kind,
            summary=summary,
            context_id=uuid4(),
        )
