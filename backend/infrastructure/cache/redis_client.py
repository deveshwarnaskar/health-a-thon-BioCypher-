"""Redis cache and ephemeral coordination adapter (Gate 05, extended Gate 09).

Provides connection management, pooling, key-value operations, and atomic
counters with deterministic in-memory fallback when Redis is unavailable.
No network calls occur at import time.

Gate 09 adds ``incr`` (atomic fixed-window counter used by the rate limiter)
and ``is_redis_available`` — note that ``ping()`` returns True even in
in-memory fallback mode, so availability must be probed explicitly.
"""

from __future__ import annotations

import threading
import time
from typing import Any


class RedisCacheAdapter:
    """Redis-backed cache adapter with optional in-memory fallback."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        socket_timeout: float = 2.0,
        client: Any = None,
        fallback_in_memory: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.socket_timeout = socket_timeout
        self.fallback_in_memory = fallback_in_memory
        self._client = client
        self._memory_cache: dict[str, tuple[bytes, float | None]] = {}
        self._memory_counters: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import redis
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    socket_timeout=self.socket_timeout,
                    socket_connect_timeout=self.socket_timeout,
                )
                self._client.ping()
            except Exception:
                if not self.fallback_in_memory:
                    raise
                self._client = False
        return self._client

    def ping(self) -> bool:
        client = self._get_client()
        if client:
            try:
                return bool(client.ping())
            except Exception:
                return False
        return True

    def is_redis_available(self) -> bool:
        """True only when a real Redis backend is reachable (not the fallback)."""
        try:
            return bool(self._get_client())
        except Exception:
            return False

    def get(self, key: str) -> bytes | None:
        client = self._get_client()
        if client:
            try:
                return client.get(key)
            except Exception:
                if not self.fallback_in_memory:
                    raise
        # In-memory fallback with TTL expiry
        if key in self._memory_cache:
            val, expiry = self._memory_cache[key]
            if expiry is not None and time.time() > expiry:
                del self._memory_cache[key]
                return None
            return val
        return None

    def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        if not isinstance(value, bytes):
            raise TypeError(f"Value must be bytes, got {type(value).__name__}")
        client = self._get_client()
        if client:
            try:
                client.set(key, value, ex=ttl_seconds)
                return
            except Exception:
                if not self.fallback_in_memory:
                    raise
        expiry = time.time() + ttl_seconds if ttl_seconds is not None else None
        self._memory_cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        client = self._get_client()
        if client:
            try:
                client.delete(key)
                return
            except Exception:
                if not self.fallback_in_memory:
                    raise
        self._memory_cache.pop(key, None)

    def incr(self, key: str, ttl_seconds: int = 60) -> int:
        """Atomically increment a fixed-window counter, returning the new value.

        On Redis this uses ``INCR`` + ``EXPIRE`` on the first request of a
        window (fixed-window approximation). The in-memory fallback resets the
        counter when its window has elapsed (sliding reset), which is what the
        offline test suite exercises.
        """
        client = self._get_client()
        if client:
            try:
                value = int(client.incr(key))
                if value == 1:
                    client.expire(key, ttl_seconds)
                return value
            except Exception:
                if not self.fallback_in_memory:
                    raise
        return self._incr_memory(key, ttl_seconds)

    def _incr_memory(self, key: str, ttl_seconds: int) -> int:
        now = time.time()
        with self._lock:
            count, window_start = self._memory_counters.get(key, (0, 0.0))
            if window_start + ttl_seconds <= now:
                count, window_start = 0, now
            count += 1
            self._memory_counters[key] = (count, window_start)
            return count

    def window_start_epoch(self, key: str, ttl_seconds: int) -> float:
        """Epoch of the current counter window start (used for reset headers;
        a best-effort fixed-window approximation on Redis)."""
        with self._lock:
            count, window_start = self._memory_counters.get(key, (0, time.time()))
            if window_start + ttl_seconds <= time.time():
                window_start = time.time()
            return window_start
