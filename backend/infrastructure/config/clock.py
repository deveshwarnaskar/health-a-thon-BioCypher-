"""Real-time system clock adapter (Gate 05).

Implements the application Clock port using Python's standard datetime module
with UTC timezone awareness.
"""

from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    """Production clock adapter returning current UTC datetime."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
