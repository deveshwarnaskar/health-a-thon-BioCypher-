"""Gate 09 — rate limiters (infrastructure).

Two ``RateLimiter`` implementations back the tier matrix (Gate 09 §9):

- ``DistributedRateLimiter`` — fixed-window ``INCR``/``EXPIRE`` over the
  counter adapter; used when distributed coordination is enabled. When the
  counter store is unreachable the tier's failure policy applies
  (FAIL_CLOSED → 429, FAIL_OPEN → allow, DEGRADE → local sliding window).
- ``InMemorySlidingWindowRateLimiter`` — a pure in-process sliding window used
  for deterministic tests and as the DEGRADE fallback.

Both produce contract ``RateLimitResult`` objects (allowed/limit/remaining/
reset_epoch/retry_after_seconds) and never expose POLICY secrets.
"""

from __future__ import annotations

import threading
import time

from backend.application.ops.contracts import (
    RateLimitFailurePolicy,
    RateLimitResult,
)

from .redis_client import RedisCacheAdapter


class InMemorySlidingWindowRateLimiter:
    """Thread-safe in-process sliding-window limiter (test/DEGRADE backend)."""

    def __init__(self) -> None:
        self._windows: dict[str, tuple[float, list[float]]] = {}
        self._lock = threading.Lock()

    def check_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        burst_allowance: int = 0,
        failure_policy: RateLimitFailurePolicy = RateLimitFailurePolicy.DEGRADE,
    ) -> RateLimitResult:
        now = time.time()
        with self._lock:
            start, hits = self._windows.get(key, (now, []))
            cutoff = now - window_seconds
            hits = [h for h in hits if h > cutoff]
            if not hits:
                start = now
            allowed = len(hits) < limit + burst_allowance
            hits.append(now)
            self._windows[key] = (start, hits)
            current = len(hits)

        reset_epoch = int(start + window_seconds)
        retry_after = max(0, int(reset_epoch - now)) + 1 if not allowed else 0
        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=max(0, limit - current),
            reset_epoch=reset_epoch,
            retry_after_seconds=retry_after,
        )


class DistributedRateLimiter:
    """Fixed-window distributed rate limiter with tiered failure behavior.

    ``counter_store`` must be a real (reachable) backend for the distributed
    path; otherwise the tier's failure policy decides the verdict so the API
    can never hang on an unavailable hint store.
    """

    def __init__(
        self,
        counter_store: RedisCacheAdapter,
        local_fallback: InMemorySlidingWindowRateLimiter | None = None,
    ) -> None:
        self._store = counter_store
        self._local = local_fallback or InMemorySlidingWindowRateLimiter()

    def check_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        burst_allowance: int = 0,
        failure_policy: RateLimitFailurePolicy = RateLimitFailurePolicy.DEGRADE,
    ) -> RateLimitResult:
        try:
            if not self._store.is_redis_available():
                raise RuntimeError("distributed counter store unavailable")
            count = self._store.incr(f"rl:{key}", window_seconds)
            reset_epoch = int(self._store.window_start_epoch(f"rl:{key}", window_seconds) + window_seconds)
            allowed = count <= limit + burst_allowance
            return RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=max(0, limit - count),
                reset_epoch=reset_epoch,
                retry_after_seconds=max(0, reset_epoch - int(time.time())) + 1 if not allowed else 0,
            )
        except Exception:
            return self._handle_failure(key, limit, window_seconds, burst_allowance, failure_policy)

    def _handle_failure(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        burst_allowance: int,
        failure_policy: RateLimitFailurePolicy,
    ) -> RateLimitResult:
        now_epoch = int(time.time())
        if failure_policy is RateLimitFailurePolicy.FAIL_CLOSED:
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_epoch=now_epoch + window_seconds,
                retry_after_seconds=window_seconds,
            )
        if failure_policy is RateLimitFailurePolicy.FAIL_OPEN:
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=max(0, limit - 1),
                reset_epoch=now_epoch + window_seconds,
                retry_after_seconds=0,
            )
        # DEGRADE → in-process sliding window.
        return self._local.check_limit(
            key, limit, window_seconds, burst_allowance, RateLimitFailurePolicy.DEGRADE
        )


__all__ = ["DistributedRateLimiter", "InMemorySlidingWindowRateLimiter"]