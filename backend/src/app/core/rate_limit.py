import redis.asyncio as aioredis
from fastapi import HTTPException, status


async def enforce_rate_limit(redis: aioredis.Redis, key: str, limit: int, window_seconds: int) -> None:
    """Fixed-window request counter backed by Redis INCR+EXPIRE. Raises 429
    once `key` has been hit more than `limit` times within the current
    `window_seconds` window. The window resets `window_seconds` after the
    first request in it, not on a wall-clock boundary."""
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window_seconds)
    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
