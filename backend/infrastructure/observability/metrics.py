"""Gate 09 — minimal operational metrics registry.

A deliberately tiny, dependency-free counter registry. When
``metrics_enabled`` is on the application records coarse operational signals
(rate-limit denials, webhook replays dropped, outbox dead letters, idempotency
conflicts, channel delivery failures) and periodically logs them as a
structured line. No external metrics sink is introduced in this gate.
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from typing import Mapping

logger = logging.getLogger(__name__)


class MetricsRegistry:
    """Thread-safe in-memory counter registry with optional log emission."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self._counters: Counter[str] = Counter()
        self._lock = threading.Lock()

    def increment(self, name: str, delta: int = 1) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._counters[name] += delta
            logger.debug("metrics counter %s += %s -> %s", name, delta, self._counters[name])

    def snapshot(self) -> Mapping[str, int]:
        with self._lock:
            return dict(self._counters)

    def emit(self) -> Mapping[str, int]:
        """Log the current snapshot as a structured line (idempotent read)."""
        snapshot = self.snapshot()
        if self.enabled and snapshot:
            logger.info("gate09 metrics snapshot: %s", snapshot)
        return snapshot

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


__all__ = ["MetricsRegistry"]