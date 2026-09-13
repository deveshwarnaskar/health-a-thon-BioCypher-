"""Redis cache and ephemeral coordination adapter (Gate 05).

Provides connection management, pooling, and key-value operations
with deterministic test fallback when Redis is unavailable.
No network calls occur at import time.
"""

from __future__ import annotations

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
