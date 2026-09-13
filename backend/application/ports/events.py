"""Event bus port (Gate 02B placeholders).

Wired in a later gate; no concrete delivery mechanism is implemented.
"""

from typing import Protocol, runtime_checkable

from ...domain.events.base import DomainEvent


@runtime_checkable
class IEventBus(Protocol):
    def publish(self, event: DomainEvent) -> None: ...