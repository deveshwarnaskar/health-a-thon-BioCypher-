"""Gate 09 — Operational resiliency application layer.

Owns the operational contracts (idempotency, deduplication, rate limiting,
immutable audit, channel orchestration, outbox worker) as pure application
concerns. This package contains NO infrastructure imports: the concrete
stores/limiters/senders implement the ports defined in ``ports.py``.
"""

from . import contracts, errors, handlers, intake_text, ports, worker
from .worker import OutboxWorker

__all__ = [
    "contracts",
    "errors",
    "handlers",
    "intake_text",
    "ports",
    "worker",
    "OutboxWorker",
]