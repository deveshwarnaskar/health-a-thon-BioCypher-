"""Clock port (Gate 04).

Injects the current timestamp into application use cases so orchestration is
deterministic and testable. Use cases must never call ``datetime.datetime.now``
directly; they ask the port. Infrastructure supplies a real clock in a later
gate; tests supply a fixed clock.
"""

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...