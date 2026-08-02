import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


async def cache_get_or_set(
    redis: aioredis.Redis,
    key: str,
    ttl_seconds: int,
    fetch_fn: Callable[[], Awaitable[Any]],
) -> Any:
    """Generic read-through cache: returns the cached JSON-decoded value for
    `key` if present, otherwise awaits `fetch_fn()` (no args), stores the
    JSON-serializable result under `key` with `ttl_seconds` TTL, and returns
    it. A cache read/write failure degrades to calling `fetch_fn()` directly
    rather than failing the caller - the cache is a performance
    optimization, not a dependency the pipeline should break on."""
    try:
        cached = await redis.get(key)
        if cached is not None:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Cache read failed for key={key}: {e}")

    result = await fetch_fn()

    try:
        await redis.set(key, json.dumps(result), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Cache write failed for key={key}: {e}")

    return result


def make_cache_key(*parts: str | None) -> str:
    """Joins cache-key components, normalizing None/empty to a stable
    placeholder so keys stay comparable across calls with partial data."""
    return ":".join(str(p) if p else "_" for p in parts)
