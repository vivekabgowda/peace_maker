"""Redis client lifecycle.

A single async Redis connection pool is created at startup and shared across
the app (cache, pub/sub, rate limiting in later sprints).
"""

from __future__ import annotations

import redis.asyncio as redis

from app.core.config import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the shared Redis client, creating the pool on first use."""
    global _client
    if _client is None:
        settings = get_settings()
        # Use the typed classmethod ``Redis.from_url`` (the module-level
        # ``redis.from_url`` is untyped in redis-py).
        _client = redis.Redis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30,
        )
    return _client


async def ping_redis() -> bool:
    """Return True if Redis responds to PING (used by the health check)."""
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


async def close_redis() -> None:
    """Close the Redis connection pool (called on shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
