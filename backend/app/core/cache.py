"""Versioned cache-aside pattern with Redis and in-memory fallback.

Rule 9: Cache with versioned keys. A Redis failure must fall through, not fail the request.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable

import orjson
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("questmf.cache")

_redis: aioredis.Redis | None = None
_in_memory_cache: dict[str, tuple[bytes, float]] = {}


async def get_redis() -> aioredis.Redis | None:
    """Get or initialize async Redis client."""
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=False,
                socket_timeout=1.0,
            )
            await _redis.ping()
            logger.info("Connected to Redis cache successfully.")
        except Exception as exc:
            logger.warning(
                "Failed to connect to Redis, falling back to in-memory/direct loader: %s", exc
            )
            _redis = None
    return _redis


async def close_redis() -> None:
    """Close Redis client."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def cached_bytes(
    ns: str,
    key_parts: tuple,
    ttl: int,
    loader: Callable[[], Awaitable[bytes]],
) -> bytes:
    """Fetch cached bytes with versioned keys. If Redis fails, fall through to loader."""
    r = await get_redis()
    key_hash = hashlib.sha1(orjson.dumps(key_parts)).hexdigest()

    if r is not None:
        try:
            ver_bytes = await r.get(f"ver:{ns}")
            ver = ver_bytes.decode() if ver_bytes else "0"
            key = f"{ns}:{ver}:{key_hash}"

            hit = await r.get(key)
            if hit is not None:
                return hit

            data = await loader()
            await r.set(key, data, ex=ttl)
            return data
        except Exception as exc:
            logger.warning("Redis error on cached_bytes (%s), falling through: %s", ns, exc)

    # Fallthrough if Redis is unavailable or threw an error
    return await loader()
