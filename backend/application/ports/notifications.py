"""Outbound messaging port (Gate 02B).

Future implementation target: ``backend.infrastructure.channel`` (WhatsApp
Cloud backend, currently ``app/server/whatsapp.py``).
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class INotificationSender(Protocol):
    def send(self, phone_number: str, text: str) -> None: ...