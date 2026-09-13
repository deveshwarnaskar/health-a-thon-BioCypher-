"""Document rendering port (Gate 02B).

Future implementation target: ``backend.infrastructure.reporting`` (ReportLab
PDF + Matplotlib charts, currently ``app/report/*``).
"""

from typing import Protocol, runtime_checkable

from ...domain.events.base import DomainEvent


@runtime_checkable
class IDocumentRenderer(Protocol):
    def render(self, context: object) -> bytes: ...
    def emit(self, event: DomainEvent) -> None: ...