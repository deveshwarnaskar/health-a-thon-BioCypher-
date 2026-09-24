"""QueueChannelMessage use case (Gate 09 §14.1).

Enqueues a provider-neutral outbound ``ChannelMessageQueued`` domain event into
the same transaction as the business state change. Delivery is asynchronous and
owned by the ``ChannelDeliveryHandler`` + outbox worker; this use case NEVER
performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping
from uuid import UUID

from ...domain.events import ChannelMessageQueued
from ..commands import (
    IngestGlucoseReading,
    LogMealDraft,
    RecordMedicationAdministration,
)
from ..ports.clock import Clock
from ..ports.events import DomainEventPublisher
from ..ports.id_generation import IdGenerator
from ..ports.unit_of_work import UnitOfWork
from ._transaction import in_transaction


@dataclass(frozen=True)
class QueueChannelMessage:
    tenant_id: UUID
    recipient_phone: str
    patient_id: UUID | None = None
    message_id: UUID | None = None
    channel_type: str = "WHATSAPP"
    template_name: str = "clinical_notification"
    template_params: Mapping[str, str] = field(default_factory=dict)
    correlation_id: UUID | None = None


@dataclass(frozen=True)
class ChannelMessageQueuedResult:
    message_id: UUID


class QueueChannelMessageHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        events: DomainEventPublisher,
        clock: Clock,
        id_gen: IdGenerator,
    ) -> None:
        self._uow = uow
        self._events = events
        self._clock = clock
        self._id_gen = id_gen

    def handle(self, cmd: QueueChannelMessage) -> ChannelMessageQueuedResult:
        return in_transaction(self._uow, lambda: self._run(cmd))

    def _run(self, cmd: QueueChannelMessage) -> ChannelMessageQueuedResult:
        message_id = cmd.message_id or self._id_gen.new_uuid()
        self._events.publish(
            ChannelMessageQueued(
                event_id=self._id_gen.new_uuid(),
                occurred_at=self._clock.now(),
                patient_id=cmd.patient_id,
                correlation_id=cmd.correlation_id,
                message_id=message_id,
                channel_type=cmd.channel_type,
                recipient_phone=cmd.recipient_phone,
                template_name=cmd.template_name,
                template_params=cmd.template_params,
            )
        )
        return ChannelMessageQueuedResult(message_id=message_id)


def delivery_hint(cmd: object) -> str:
    """A coarse, PHI-free delivery-kind label used by caller code/tests."""
    if isinstance(cmd, RecordMedicationAdministration):
        return "MEDICATION_NOTIFICATION"
    if isinstance(cmd, IngestGlucoseReading):
        return "GLUCOSE_ACKNOWLEDGEMENT"
    if isinstance(cmd, LogMealDraft):
        return "MEAL_DRAFT_ACKNOWLEDGEMENT"
    return "CLINICAL_NOTIFICATION"