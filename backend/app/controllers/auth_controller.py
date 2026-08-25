import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.controllers.deps import get_current_user_id
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserDTO
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    result = await service.login(req)
    logger.info("Login successful: %s", req.username)
    return ApiResponse(data=result)


@router.post("/register", response_model=ApiResponse[UserDTO])
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    result = await service.register(req)
    return ApiResponse(data=result)


@router.get("/me", response_model=ApiResponse[UserDTO])
async def get_me(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    result = await service.get_current_user(user_id)
    return ApiResponse(data=result)
