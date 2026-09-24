"""Application-layer metrics port (additive multimodal layer).

The application layer must never import infrastructure (see
``APPLICATION_FORBIDDEN`` in the architecture boundaries test). Operational
metrics are therefore consumed through this narrow, PHI-free Protocol; the
worker wires the Prometheus registry in via an infrastructure adapter, and tests
inject ``NullApplicationMetrics`` (or a recording fake).

Label keys are fixed and low-cardinality — nothing patient-identifying ever
reaches a label or a counter value.
"""
from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable


@runtime_checkable
class ApplicationMetrics(Protocol):
    def increment_counter(
        self, name: str, labels: Mapping[str, str] | None = None, delta: float = 1.0
    ) -> None: ...

    def observe_histogram(
        self, name: str, value: float, labels: Mapping[str, str] | None = None
    ) -> None: ...


class NullApplicationMetrics:
    """No-op implementation used whenever no metrics adapter is wired."""

    def increment_counter(self, name: str, labels: Mapping[str, str] | None = None, delta: float = 1.0) -> None:
        return None

    def observe_histogram(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        return None


__all__ = ["ApplicationMetrics", "NullApplicationMetrics"]