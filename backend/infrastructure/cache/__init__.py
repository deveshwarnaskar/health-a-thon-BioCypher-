"""Cache infrastructure package (Gate 05)."""

from .redis_client import RedisCacheAdapter

__all__ = ["RedisCacheAdapter"]