"""Gate 09 — unit tests: rate limiters and tier policies.

Covers the in-memory sliding window, the distributed limiter's failure
policies (FAIL_CLOSED / FAIL_OPEN / DEGRADE), and the tier matrix wiring.

NOTE: deliberately no ``from __future__ import annotations`` here — FastAPI
treats deferred string annotations of ``Request``/``Response`` as query params,
breaking the endpoint used in ``test_apply_rate_limit_raises_when_denied``.
"""

import time

from backend.application.ops.contracts import RateLimitFailurePolicy, RateLimitResult
from backend.application.ops.errors import RateLimitExceeded
from backend.infrastructure.cache.rate_limiter import (
    DistributedRateLimiter,
    InMemorySlidingWindowRateLimiter,
)


class _UnreachableCounterStore:
    """A counter store that always reports Redis as unavailable."""

    def is_redis_available(self) -> bool:
        return False

    def incr(self, key: str, ttl_seconds: int = 60) -> int:
        raise RuntimeError("unreachable")

    def window_start_epoch(self, key: str, ttl_seconds: int) -> float:
        raise RuntimeError("unreachable")


class TestInMemorySlidingWindow:
    def test_allows_requests_under_limit(self):
        limiter = InMemorySlidingWindowRateLimiter()
        results = [limiter.check_limit("k", 3, 60) for _ in range(3)]
        assert all(r.allowed for r in results)
        assert [r.remaining for r in results] == [2, 1, 0]

    def test_denies_above_limit_with_retry_after(self):
        limiter = InMemorySlidingWindowRateLimiter()
        r = limiter.check_limit("k", 2, 60)
        assert r.allowed
        r = limiter.check_limit("k", 2, 60)
        assert r.allowed
        denied = limiter.check_limit("k", 2, 60)
        assert not denied.allowed
        assert denied.remaining == 0
        assert denied.retry_after_seconds >= 1

    def test_window_resets_after_elapse(self):
        limiter = InMemorySlidingWindowRateLimiter()
        assert limiter.check_limit("k", 1, 1).allowed
        denied = limiter.check_limit("k", 1, 1)
        assert not denied.allowed
        time.sleep(1.1)
        assert limiter.check_limit("k", 1, 1).allowed

    def test_burst_allowance_admits_extra_requests(self):
        limiter = InMemorySlidingWindowRateLimiter()
        for _ in range(4):  # limit 3 + burst 1
            r = limiter.check_limit("k", 3, 60, burst_allowance=1)
            assert r.allowed
        denied = limiter.check_limit("k", 3, 60, burst_allowance=1)
        assert not denied.allowed

    def test_keys_are_independent(self):
        limiter = InMemorySlidingWindowRateLimiter()
        limiter.check_limit("a", 1, 60)
        assert limiter.check_limit("b", 1, 60).allowed


class TestDistributedFailurePolicies:
    def test_fail_closed_denies_when_store_unavailable(self):
        limiter = DistributedRateLimiter(_UnreachableCounterStore())
        r = limiter.check_limit(
            "k", 10, 60, 0, RateLimitFailurePolicy.FAIL_CLOSED
        )
        assert not r.allowed
        assert r.retry_after_seconds == 60

    def test_fail_open_allows_when_store_unavailable(self):
        limiter = DistributedRateLimiter(_UnreachableCounterStore())
        r = limiter.check_limit("k", 10, 60, 0, RateLimitFailurePolicy.FAIL_OPEN)
        assert r.allowed

    def test_degrade_falls_back_to_local_window(self):
        limiter = DistributedRateLimiter(_UnreachableCounterStore())
        r = limiter.check_limit(
            "k", 2, 60, 0, RateLimitFailurePolicy.DEGRADE
        )
        assert r.allowed
        r2 = limiter.check_limit("k", 2, 60, 0, RateLimitFailurePolicy.DEGRADE)
        assert r2.allowed
        r3 = limiter.check_limit("k", 2, 60, 0, RateLimitFailurePolicy.DEGRADE)
        assert not r3.allowed


class TestTierMatrix:
    def test_webhook_tier_is_fail_open(self):
        from backend.interfaces.http.ops.rate_limit import TIERS

        assert TIERS["webhook"].policy is RateLimitFailurePolicy.FAIL_OPEN
        assert TIERS["webhook"].window_seconds == 1
        assert TIERS["webhook"].limit == 100

    def test_auth_tier_is_fail_closed(self):
        from backend.interfaces.http.ops.rate_limit import TIERS

        assert TIERS["auth"].policy is RateLimitFailurePolicy.FAIL_CLOSED
        assert TIERS["auth"].limit == 10

    def test_ai_tier_fail_closed(self):
        from backend.interfaces.http.ops.rate_limit import TIERS

        assert TIERS["ai"].policy is RateLimitFailurePolicy.FAIL_CLOSED

    def test_apply_rate_limit_raises_when_denied(self):
        from fastapi import FastAPI, Request, Response
        from fastapi.testclient import TestClient

        from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit

        app = FastAPI()

        @app.exception_handler(RateLimitExceeded)
        async def _rl(request, exc):
            return Response(
                status_code=429,
                content="too many",
                headers={"Retry-After": str(exc.result.retry_after_seconds)},
            )

        limiter = InMemorySlidingWindowRateLimiter()

        @app.get("/x")
        def x(request: Request, response: Response):
            apply_rate_limit(
                request=request,
                response=response,
                tier=TIERS["auth"],
                limiter=limiter,
                ctx=_FakeCtx(),
            )
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        allowed = sum(1 for _ in range(TIERS["auth"].limit + TIERS["auth"].burst)
                      if client.get("/x").status_code == 200)
        resp = client.get("/x")
        assert resp.status_code == 429
        assert resp.headers.get("retry-after") is not None


class _FakeCtx:
    tenant_id = "00000000-0000-0000-0000-000000000042"