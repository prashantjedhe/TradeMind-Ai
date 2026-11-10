import hashlib

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from app.services import rate_limiter
from app.api.v1 import auth
from app.schemas.auth import RefreshRequest, UserLoginRequest, UserRegisterRequest


class FakeRedis:
    def __init__(self, result):
        self.result = result
        self.call = None

    async def eval(self, script, key_count, key, window_seconds):
        self.call = (script, key_count, key, window_seconds)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def make_request(host="203.0.113.7"):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [],
            "client": (host, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "http_version": "1.1",
        }
    )


@pytest.mark.asyncio
async def test_rate_limiter_uses_atomic_expiring_counter(monkeypatch):
    redis_client = FakeRedis(result=3)
    monkeypatch.setattr(rate_limiter, "redis_client", redis_client)

    await rate_limiter.enforce_rate_limit("auth:login:client", 5, 60)

    script, key_count, key, window = redis_client.call
    assert "INCR" in script
    assert "EXPIRE" in script
    assert key_count == 1
    assert key == "ratelimit:auth:login:client"
    assert window == 60


@pytest.mark.asyncio
async def test_rate_limiter_rejects_excess_requests(monkeypatch):
    monkeypatch.setattr(rate_limiter, "redis_client", FakeRedis(result=6))

    with pytest.raises(HTTPException) as exc:
        await rate_limiter.enforce_rate_limit("orders:user", 5, 60)

    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limiter_reports_redis_outage(monkeypatch):
    monkeypatch.setattr(
        rate_limiter,
        "redis_client",
        FakeRedis(result=RedisConnectionError("redis unavailable")),
    )

    with pytest.raises(HTTPException) as exc:
        await rate_limiter.enforce_rate_limit("orders:user", 5, 60)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_auth_login_is_rate_limited_before_database_access(monkeypatch):
    calls = []

    async def reject_request(**kwargs):
        calls.append(kwargs)
        raise HTTPException(status_code=429, detail="too many attempts")

    monkeypatch.setattr(auth, "enforce_rate_limit", reject_request)

    with pytest.raises(HTTPException) as exc:
        await auth.login(
            UserLoginRequest(email="Trader@Example.com", password="not-a-real-password"),
            make_request(),
            db=object(),
        )

    assert exc.value.status_code == 429
    assert calls[0]["key"].startswith("auth:login:203.0.113.7:")
    assert calls[0]["max_requests"] == auth.AUTH_LOGIN_LIMIT


@pytest.mark.asyncio
async def test_auth_registration_rate_limit_is_scoped_to_email(monkeypatch):
    calls = []

    async def reject_request(**kwargs):
        calls.append(kwargs)
        raise HTTPException(status_code=429, detail="too many attempts")

    monkeypatch.setattr(auth, "enforce_rate_limit", reject_request)

    with pytest.raises(HTTPException):
        await auth.register(
            UserRegisterRequest(
                email="Trader@Example.com",
                username="trader",
                password="long-enough-password",
            ),
            db=object(),
        )

    digest = hashlib.sha256(b"trader@example.com").hexdigest()
    assert calls[0]["key"] == f"auth:register:{digest}"
    assert calls[0]["max_requests"] == auth.AUTH_REGISTER_LIMIT


@pytest.mark.asyncio
async def test_auth_refresh_rate_limit_is_scoped_to_token(monkeypatch):
    calls = []

    async def reject_request(**kwargs):
        calls.append(kwargs)
        raise HTTPException(status_code=429, detail="too many attempts")

    monkeypatch.setattr(auth, "enforce_rate_limit", reject_request)

    with pytest.raises(HTTPException):
        await auth.refresh(RefreshRequest(refresh_token="not-a-real-token"))

    digest = hashlib.sha256(b"not-a-real-token").hexdigest()
    assert calls[0]["key"] == f"auth:refresh:{digest}"
    assert calls[0]["max_requests"] == auth.AUTH_REFRESH_LIMIT
