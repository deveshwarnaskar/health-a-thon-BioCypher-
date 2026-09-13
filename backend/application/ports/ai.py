"""AI application port (Gate 04).

Provider-neutral (no Gemini/OpenAI/any provider SDK). Application treats AI
output as a DRAFT only. Generation never equals approval: the port returns an
unapproved ``ArtifactDraft``; human review happens in the ``ReviewAIArtifact``
use case through the domain review-state machine.

Infrastructure supplies a provider-backed implementation in a later gate; tests
supply a deterministic fake.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ArtifactDraft:
    """AI-produced synthesis/extraction. Carries NO approval semantics."""

    artifact_kind: str = "extracted_observation"
    summary: str = ""
    context_id: UUID = field(default_factory=uuid4)


@runtime_checkable
class AIArtifactGenerator(Protocol):
    def generate(self, context: str, patient_id: UUID) -> ArtifactDraft: ...