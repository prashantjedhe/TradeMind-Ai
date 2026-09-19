from fastapi import APIRouter, Depends

from app.models.user import User
from app.schemas.auth import UserResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
