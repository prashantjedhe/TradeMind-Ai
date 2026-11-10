import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    RefreshRequest,
)
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.api.deps import get_current_user, blacklist_token, oauth2_scheme
from app.services.rate_limiter import enforce_rate_limit

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

AUTH_LOGIN_LIMIT = 5
AUTH_LOGIN_WINDOW_SECONDS = 60
AUTH_REGISTER_LIMIT = 10
AUTH_REGISTER_WINDOW_SECONDS = 3600
AUTH_REFRESH_LIMIT = 30
AUTH_REFRESH_WINDOW_SECONDS = 60


def _client_host(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    email_digest = hashlib.sha256(payload.email.strip().lower().encode()).hexdigest()
    await enforce_rate_limit(
        key=f"auth:register:{email_digest}",
        max_requests=AUTH_REGISTER_LIMIT,
        window_seconds=AUTH_REGISTER_WINDOW_SECONDS,
    )
    existing = await db.execute(
        select(User).where((User.email == payload.email) | (User.username == payload.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email or username already registered")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    email_digest = hashlib.sha256(payload.email.strip().lower().encode()).hexdigest()
    await enforce_rate_limit(
        key=f"auth:login:{_client_host(request)}:{email_digest}",
        max_requests=AUTH_LOGIN_LIMIT,
        window_seconds=AUTH_LOGIN_WINDOW_SECONDS,
    )
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest):
    token_digest = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    await enforce_rate_limit(
        key=f"auth:refresh:{token_digest}",
        max_requests=AUTH_REFRESH_LIMIT,
        window_seconds=AUTH_REFRESH_WINDOW_SECONDS,
    )
    try:
        decoded = decode_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = decoded.get("sub")
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials=Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
):
    token = credentials.credentials
    payload = decode_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")

    if jti and exp:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        ttl = max(exp - now_ts, 1)
        await blacklist_token(jti, ttl)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
