"""Observability request/execution context management (Gate 10P-D).

Thread-safe, async-safe context variables for correlation and request IDs.
Enables automatic propagation into structured logging and tracing spans
without manual argument threading through application layers.
"""

from __future__ import annotations

from contextvars import ContextVar

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_correlation_id() -> str:
    """Return the active correlation ID or an empty string."""
    return correlation_id_ctx.get()


def set_correlation_id(correlation_id: str):
    """Set the active correlation ID for the current async task / context."""
    return correlation_id_ctx.set(correlation_id)


def get_request_id() -> str:
    """Return the active request ID or an empty string."""
    return request_id_ctx.get()


def set_request_id(request_id: str):
    """Set the active request ID for the current async task / context."""
    return request_id_ctx.set(request_id)
