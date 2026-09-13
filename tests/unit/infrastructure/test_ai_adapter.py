"""Tests for Provider-Neutral AI Adapter (Gate 05).

Verifies:
1. Conformance to AIArtifactGenerator port.
2. Production of unapproved ArtifactDrafts only.
3. No automatic approval, actioning, or prescription semantics.
"""

from uuid import uuid4

from backend.application.ports.ai import AIArtifactGenerator, ArtifactDraft
from backend.infrastructure.ai.adapter import ProviderNeutralAIAdapter


def test_ai_adapter_implements_port_protocol():
    adapter = ProviderNeutralAIAdapter()
    assert isinstance(adapter, AIArtifactGenerator)


def test_generate_returns_unapproved_draft():
    adapter = ProviderNeutralAIAdapter()
    patient_id = uuid4()
    context = "Patient ate 2 rotis and a bowl of dal at 1 PM"

    draft = adapter.generate(context, patient_id)

    assert isinstance(draft, ArtifactDraft)
    assert draft.artifact_kind == "extracted_observation"
    assert "Synthesized draft from input" in draft.summary
    assert draft.context_id is not None
    # Verify no approval attributes exist on draft
    assert not hasattr(draft, "approved")
    assert not hasattr(draft, "state")
