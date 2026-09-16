"""Gate 09 — operational HTTP capabilities (interfaces layer).

Brings the application-layer operational ports into the HTTP stack without
adding business logic to routes:

- ``idempotency``  — idempotency-key reservation middleware + safe headers
- ``rate_limit``   — tiered rate limiting (disabled until explicitly enabled)
- ``audit``        — atomic, tenant-scoped compliance record dependencies

Policy keys stay in ``backend/application/ops``; this package only wires them,
following the boundary documented in ``ARCHITECTURE.md``.
"""

from __future__ import annotations

from .audit import audit_dependency, json_field
from .rate_limit import TIERS, RateTier, apply_rate_limit, get_rate_limiter
from .idempotency import IdempotencyMiddleware, build_fingerprint

__all__ = [
    "IdempotencyMiddleware",
    "TIERS",
    "RateTier",
    "apply_rate_limit",
    "audit_dependency",
    "build_fingerprint",
    "get_rate_limiter",
    "json_field",
]