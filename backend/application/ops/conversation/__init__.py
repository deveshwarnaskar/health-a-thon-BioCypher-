"""Conversational AI/ML layer for the WhatsApp channel (spec §0–§40).

Additive to the existing Gate 09 worker: the ``ConversationEngine`` is an
opt-in capability injected into ``WhatsAppIntakeHandler``. When it is not
present every existing branch (glucose, meal, confirm, cancel, status, help,
unsupported) runs exactly as before — the existing pipeline is deliberately
left untouched.

Design invariants (§1, §19, §33):
- THALI domain services/entities remain the only writers of clinical state.
- Deterministic logic is authoritative: identity, persistence, reminders,
  nutrition, safety gates. AI is used ONLY for NLU intent resolution, value
  extraction from free text, and the wording of neutral replies.
- The engine NEVER persists anything the patient has not confirmed.
"""

from .engine import ConversationEngine, EngineOutcome
from backend.infrastructure.parsing.conversation.taxonomy import ConversationIntent

__all__ = [
    "ConversationEngine",
    "ConversationIntent",
    "EngineOutcome",
]