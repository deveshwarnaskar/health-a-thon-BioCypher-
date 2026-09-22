"""No-PHI telemetry counters (spec §32).

Counters carry intent categories, confidence buckets, and safety outcomes — not
raw message text, not patient identifiers. The engine increments counters with
an in-memory monotonic clock; an optional sink can ship them to metrics.
"""

from __future__ import annotations

import threading
from collections import Counter

from backend.infrastructure.parsing.conversation.schema import SafetyFlag, StructuredIntent
from backend.infrastructure.parsing.conversation.taxonomy import ConversationIntent


class ConversationTelemetry:
    """Thread-safe monotonic counters, entirely PHI-free."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.messages_seen = 0
        self.engine_handled = 0
        self.legacy_deferred = 0
        self.by_intent: Counter[str] = Counter()
        self.by_confidence: Counter[str] = Counter()
        self.by_safety: Counter[str] = Counter()
        self.emergency_count = 0
        self.ai_online_count = 0
        self.ai_fallback_count = 0

    def message_seen(self) -> None:
        with self._lock:
            self.messages_seen += 1

    def engine_handled_message(self) -> None:
        with self._lock:
            self.engine_handled += 1

    def legacy_deferred_message(self) -> None:
        with self._lock:
            self.legacy_deferred += 1

    def record_intent(self, intent: ConversationIntent) -> None:
        with self._lock:
            self.by_intent[intent.value] += 1

    def record_confidence(self, confidence: str) -> None:
        with self._lock:
            self.by_confidence[confidence] += 1

    def record_safety(self, flag: SafetyFlag | None) -> None:
        with self._lock:
            self.by_safety[flag.value if flag else "none"] += 1

    def record_emergency(self) -> None:
        with self._lock:
            self.emergency_count += 1

    def record_ai_online(self) -> None:
        with self._lock:
            self.ai_online_count += 1

    def record_ai_fallback(self) -> None:
        with self._lock:
            self.ai_fallback_count += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "messages_seen": self.messages_seen,
                "engine_handled": self.engine_handled,
                "legacy_deferred": self.legacy_deferred,
                "by_intent": dict(self.by_intent),
                "by_confidence": dict(self.by_confidence),
                "by_safety": dict(self.by_safety),
                "emergency_count": self.emergency_count,
                "ai_online_count": self.ai_online_count,
                "ai_fallback_count": self.ai_fallback_count,
            }


__all__ = ["ConversationTelemetry"]