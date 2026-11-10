"""
Simple fixed-window rate limiter backed by Redis.

Uses the same redis_client instance as the rest of the app (JWT
blacklist, price cache) rather than a separate connection pool.
"""

from redis.exceptions import RedisError
from fastapi import HTTPException, status

from app.api.deps import redis_client

RATE_LIMIT_PREFIX = "ratelimit:"
INCREMENT_AND_EXPIRE = """
local count = redis.call('INCR', KEYS[1])
if count == 1 or redis.call('TTL', KEYS[1]) < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


async def enforce_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """
    Fixed-window limiter: allows `max_requests` per `window_seconds`
    for the given key. Raises HTTP 429 if the limit is exceeded.
    """
    redis_key = f"{RATE_LIMIT_PREFIX}{key}"
    try:
        current = await redis_client.eval(
            INCREMENT_AND_EXPIRE, 1, redis_key, window_seconds
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting is temporarily unavailable.",
        ) from exc

    if current > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {max_requests} requests per {window_seconds}s",
        )
