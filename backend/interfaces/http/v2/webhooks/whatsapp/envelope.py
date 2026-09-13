"""Neutral inbound channel envelope (Gate 06).

The WhatsApp webhook boundary MUST NOT contain clinical business rules. It
normalizes verified provider events into a channel-agnostic envelope that the
application layer can later dispatch. Nothing PHI-bearing or raw is persisted
by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class WhatsAppInboundEnvelope:
    """Channel-neutral representation of one verified WhatsApp event."""

    event_id: UUID = field(default_factory=uuid4)
    message_id: str = ""
    source_phone: str = ""
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_event(cls, *, message_id: str, source_phone: str, event_type: str) -> "WhatsAppInboundEnvelope":
        return cls(message_id=message_id, source_phone=source_phone, event_type=event_type)
