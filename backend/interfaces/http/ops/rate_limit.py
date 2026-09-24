"""Gate 09 — tiered rate limiting (HTTP dependency layer).

Tier matrix (contract §9):

- auth:            10/min, burst 2,  FAIL_CLOSED
- webhook:        100/s,   burst 20, FAIL_OPEN   (signature-verified only)
- ai:              20/min, burst 5,  FAIL_CLOSED
- clinical_write:  60/min, burst 10, DEGRADE
- admin:           30/min, burst 5,  FAIL_CLOSED
- read:           120/min, burst 30, DEGRADE

Rate limiting is DISABLED by default (``RedisConfig.enabled`` is False), in
which case ``get_rate_limiter()`` returns None and routes enforce nothing. When
enabled, a live Redis backend serves the fixed-window counters and the tier
failure policy governs Redis outages.

The ``apply_rate_limit`` helper enriches the response with the standard
``X-RateLimit-*`` headers and raises ``RateLimitExceeded`` (mapped to 429) when
the allowance is exhausted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.ops.contracts import RateLimitFailurePolicy

if TYPE_CHECKING:
    from backend.interfaces.http.v2.security.authorization import AuthenticatedContext

# Sentinel so the limiter is built at most once per process (tests override the
# dependency function directly).
_limiter_built = False
_limiter = None


@dataclass(frozen=True)
class RateTier:
    """One throttled operation class."""

    name: str
    limit: int
    window_seconds: int
    burst: int = 0
    policy: RateLimitFailurePolicy = RateLimitFailurePolicy.DEGRADE


TIERS: dict[str, RateTier] = {
    "auth": RateTier("auth", 10, 60, burst=2, policy=RateLimitFailurePolicy.FAIL_CLOSED),
    "webhook": RateTier("webhook", 100, 1, burst=20, policy=RateLimitFailurePolicy.FAIL_OPEN),
    "ai": RateTier("ai", 20, 60, burst=5, policy=RateLimitFailurePolicy.FAIL_CLOSED),
    "clinical_write": RateTier("clinical_write", 60, 60, burst=10, policy=RateLimitFailurePolicy.DEGRADE),
    "admin": RateTier("admin", 30, 60, burst=5, policy=RateLimitFailurePolicy.FAIL_CLOSED),
    "read": RateTier("read", 120, 60, burst=30, policy=RateLimitFailurePolicy.DEGRADE),
}


def get_rate_limiter():
    """Return the configured limiter, or None when rate limiting is disabled.

    Disabled by default (``RedisConfig.enabled=False``). Dependency-overridable
    in tests so a memory limiter can be injected deterministically.
    """
    global _limiter_built, _limiter
    if not _limiter_built:
        _limiter_built = True
        from config.settings import Settings

        settings = Settings()
        if settings.redis.enabled:
            from backend.infrastructure.cache.rate_limiter import DistributedRateLimiter
            from backend.infrastructure.cache.redis_client import RedisCacheAdapter

            _limiter = DistributedRateLimiter(
                RedisCacheAdapter(
                    host=settings.redis.host,
                    port=settings.redis.port,
                    db=settings.redis.db,
                    password=settings.redis.password,
                ),
            )
    return _limiter


def apply_rate_limit(
    *,
    request,
    response,
    tier: RateTier,
    limiter,
    ctx: "AuthenticatedContext | None" = None,
    scope_key: str | None = None,
) -> None:
    """Check the tier allowance and write the standard rate-limit headers.

    When the limiter is None (feature disabled) this is a no-op. ``scope_key``
    overrides the tenant-scoped key for provider-facing tiers (e.g. the webhook
    source phone). Raises ``RateLimitExceeded`` on denial.
    """
    from backend.application.ops.errors import RateLimitExceeded

    if limiter is None:
        return

    if scope_key:
        key = f"{tier.name}:{scope_key}"
    elif ctx is not None:
        key = f"{tier.name}:{ctx.tenant_id}"
    else:
        return

    result = limiter.check_limit(
        key,
        tier.limit,
        tier.window_seconds,
        tier.burst,
        tier.policy,
    )
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(result.reset_epoch)
    if not result.allowed:
        response.headers["Retry-After"] = str(result.retry_after_seconds)
        raise RateLimitExceeded(result)


__all__ = ["TIERS", "RateTier", "apply_rate_limit", "get_rate_limiter"]