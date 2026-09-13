"""Domain event publication port (Gate 04).

Canonical append-only domain events are published outward through this port.
It is intentionally NOT a general-purpose event JSON mechanism: entities keep
their current state, audit and telemetry stay separate (see domain/events/base).
Infrastructure provides the concrete delivery mechanism in a later gate.
"""

from typing import Protocol, runtime_checkable

from ...domain.events.base import DomainEvent


@runtime_checkable
class DomainEventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...