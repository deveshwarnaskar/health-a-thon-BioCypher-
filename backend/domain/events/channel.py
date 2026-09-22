"""Channel orchestration domain events (Gate 03, extended Gate 09).

``ChannelMessageQueued`` marks "the system queued an outbound channel message".
It is a domain-framed, provider-neutral signal consumed exclusively through the
transactional outbox; the actual HTTP call to a channel provider is owned by the
infrastructure ``ChannelSender`` port and never touches the domain.
"""

from dataclasses import dataclass, field
from typing import Mapping
from uuid import UUID, uuid4

from .base import DomainEvent

CHANNEL_MESSAGE_SEND_EVENT_TYPE = "channel.message.send"
WEBHOOK_MESSAGE_RECEIVED_EVENT_TYPE = "whatsapp.message.received"


@dataclass(frozen=True)
class ChannelMessageQueued(DomainEvent):
    event_type: str = CHANNEL_MESSAGE_SEND_EVENT_TYPE
    message_id: UUID = field(default_factory=uuid4)
    channel_type: str = "WHATSAPP"
    recipient_phone: str = ""
    template_name: str = "clinical_notification"
    template_params: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WhatsAppMessageReceived(DomainEvent):
    """One signature-verified, deduplicated inbound WhatsApp message.

    Written to the transactional outbox with a NULL tenant binding; the worker
    resolves the sender phone to a (tenant, patient) anchor inside the
    privileged routing function before any domain work happens.
    """

    event_type: str = WEBHOOK_MESSAGE_RECEIVED_EVENT_TYPE
    message_id: str = ""
    source_phone: str = ""
    text: str = ""
    provider: str = "whatsapp"
    recipient_phone_number_id: str = ""
    timestamp: int | None = None
    message_type: str = "text"
    interactive_reply_id: str | None = None
    media_type: str | None = None
    media_id: str | None = None
    caption: str | None = None