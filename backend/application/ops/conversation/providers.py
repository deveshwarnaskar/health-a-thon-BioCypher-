"""AI provider abstraction for the conversational layer (spec §33/§34).

The engine NEVER depends on a particular model. ``ConversationAIProvider`` is
the seam. The default wiring supplies a deterministic provider that returns
``None`` (turn off AI) so the entire pipeline runs offline and deterministically.

Sarvam (or any future model) is adapted behind ``SarvamConversationProvider``,
which:

- never raises into the engine (catches and returns ``None``),
- returns only the structured contract (L2 prompt), and
- lets deterministic extraction overrule any AI-collected value.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from backend.infrastructure.parsing.conversation.extractors import normalize_digits
from backend.infrastructure.parsing.conversation.schema import (
    Confidence,
    ProvenanceSource,
    StructuredIntent,
)
from .prompts import EXTRACTION_SYSTEM_L2_PROMPT

logger = logging.getLogger(__name__)


class ConversationAIProvider(Protocol):
    """Minimal provider surface used by the engine."""

    def complete(self, *, system: str, user: str) -> str | None: ...

    def is_configured(self) -> bool: ...


class DeterministicConversationProvider:
    """Offline provider: no AI. Deterministic extraction is the only path."""

    def is_configured(self) -> bool:
        return False

    def complete(self, *, system: str, user: str) -> str | None:
        return None


class SarvamConversationProvider:
    """Adapter over the existing Sarvam client (duck-typed, never imported hard)."""

    def __init__(self, client: Any, *, temperature: float = 0.0, max_tokens: int = 400) -> None:
        self._client = client
        self._temperature = temperature
        self._max_tokens = max_tokens

    def is_configured(self) -> bool:
        try:
            return bool(self._client.is_configured)
        except AttributeError:
            return self._client is not None

    def complete(self, *, system: str, user: str) -> str | None:
        if self._client is None:
            return None
        try:
            res = self._client.chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            return str(res.get("content", "")).strip() or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("sarvam conversation completion failed: %s", exc)
            return None


def ai_extract_intent(
    provider: ConversationAIProvider,
    text: str,
    fallback: StructuredIntent,
) -> None:
    """Ask the provider to corroborate extraction; deterministic always wins.

    ``fallback`` is the deterministic ``StructuredIntent``. We only enrich AI
    values that the deterministic layer could not anchor, and even then only as
    a proposal — the caller decides whether to place it behind a confirmation.
    """
    if provider is None or not provider.is_configured():
        return
    try:
        raw = provider.complete(
            system=EXTRACTION_SYSTEM_L2_PROMPT,
            user=normalize_digits(text),
        )
        if not raw:
            return
        import json

        payload = json.loads(raw)
    except (ValueError, TypeError) as exc:
        logger.info("ai extraction non-json (%s); deterministic kept", exc)
        return

    def _safe_glucose() -> str | None:
        g = payload.get("glucose") or {}
        v = g.get("value_mg_dl")
        if isinstance(v, int) and 20 <= v <= 600 and fallback.glucose.value_mg_dl is None:
            return str(v)
        return None

    value = _safe_glucose()
    if value is not None:
        fallback.glucose.value_mg_dl = int(value)
        fallback.glucose.confidence = Confidence.MID
        fallback.glucose.provenance = ProvenanceSource.AI_ASSISTED


__all__ = [
    "ConversationAIProvider",
    "DeterministicConversationProvider",
    "SarvamConversationProvider",
    "ai_extract_intent",
]