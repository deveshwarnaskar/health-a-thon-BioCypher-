"""Gate 09 — Operational error taxonomy.

These errors are raised by the application-layer operational boundaries and
mapped to safe HTTP responses by the interfaces layer. None of them carry
secrets, PHI, or raw provider payloads.
"""

from __future__ import annotations

from typing import Mapping

from .contracts import RateLimitResult


class OpsError(Exception):
    """Base class for operational policy errors."""


class IdempotencyKeyMismatch(OpsError):
    """The same idempotency key was reused with a different request payload."""


class ConcurrentIdempotencyConflict(OpsError):
    """A request with this idempotency key is currently being processed."""


class IdempotentReplay(OpsError):
    """An exact retry whose previously-completed response must be returned."""

    def __init__(
        self,
        *,
        status_code: int,
        headers: Mapping[str, str] | None,
        body: str | None,
    ) -> None:
        super().__init__("idempotency replay")
        self.status_code = status_code
        self.headers = headers or {}
        self.body = body or ""


class RateLimitExceeded(OpsError):
    """The request exceeded the tier allowance (HTTP 429)."""

    def __init__(self, result: RateLimitResult) -> None:
        super().__init__("rate limit exceeded")
        self.result = result


class TransientWorkerError(OpsError):
    """A worker operation failed transiently and may be retried."""


class PermanentWorkerFailure(OpsError):
    """A worker operation can never succeed; retrying will not help."""