"""Tests for Redis Cache Adapter (Gate 05).

Verifies:
1. Cache get, set, delete operations.
2. TTL expiration semantics.
3. Type safety (enforces bytes payload).
4. Ping health check.
5. In-memory fallback when external Redis is unavailable.
"""

import time
import pytest

from backend.infrastructure.cache.redis_client import RedisCacheAdapter


def test_cache_set_and_get():
    cache = RedisCacheAdapter(fallback_in_memory=True)
    cache.set("test_key", b"test_value")

    assert cache.get("test_key") == b"test_value"
    assert cache.get("non_existent_key") is None


def test_cache_delete():
    cache = RedisCacheAdapter(fallback_in_memory=True)
    cache.set("to_delete", b"delete_me")
    assert cache.get("to_delete") == b"delete_me"

    cache.delete("to_delete")
    assert cache.get("to_delete") is None


def test_cache_ttl_expiry():
    cache = RedisCacheAdapter(fallback_in_memory=True)
    cache.set("short_lived", b"data", ttl_seconds=1)

    assert cache.get("short_lived") == b"data"
    time.sleep(1.1)
    assert cache.get("short_lived") is None


def test_cache_type_safety():
    cache = RedisCacheAdapter(fallback_in_memory=True)
    with pytest.raises(TypeError, match="must be bytes"):
        cache.set("key", "not_bytes")  # type: ignore


def test_cache_ping():
    cache = RedisCacheAdapter(fallback_in_memory=True)
    assert cache.ping() is True
