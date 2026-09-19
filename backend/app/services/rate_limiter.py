"""
Simple fixed-window rate limiter backed by Redis.

Uses the same redis_client instance as the rest of the app (JWT
blacklist, price cache) rather than a separate connection pool.
"""

from fastapi import HTTPException, status

from app.api.deps import redis_client

RATE_LIMIT_PREFIX = "ratelimit:"


async def enforce_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """
    Fixed-window limiter: allows `max_requests` per `window_seconds`
    for the given key. Raises HTTP 429 if the limit is exceeded.
    """
    redis_key = f"{RATE_LIMIT_PREFIX}{key}"
    current = await redis_client.incr(redis_key)

    if current == 1:
        # First request in this window - set the expiry.
        await redis_client.expire(redis_key, window_seconds)

    if current > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {max_requests} requests per {window_seconds}s",
        )
