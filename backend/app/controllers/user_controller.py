import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.controllers.deps import require_admin, CurrentUser
from app.schemas.auth import UserDTO
from app.schemas.common import ApiResponse, PageResponse
from app.schemas.user import UserCreateRequest, UserUpdateRequest
from app.services.user_service import UserService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["User Management"])


@router.get("", response_model=ApiResponse[PageResponse[UserDTO]])
async def list_users(
    page: int = 1,
    page_size: int = 20,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    result = await service.list_users(page, page_size)
    return ApiResponse(data=result)


@router.post("", response_model=ApiResponse[UserDTO])
async def create_user(
    req: UserCreateRequest,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    result = await service.create_user(req)
    logger.info("User created by admin %s: %s", admin.username, req.username)
    return ApiResponse(data=result)


@router.put("/{user_id}", response_model=ApiResponse[UserDTO])
async def update_user(
    user_id: int,
    req: UserUpdateRequest,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    result = await service.update_user(user_id, req)
    return ApiResponse(data=result)


@router.delete("/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: int,
    admin: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    await service.delete_user(user_id, admin.id)
    logger.info("User deleted by admin %s: id=%d", admin.username, user_id)
    return ApiResponse(message="Deleted successfully")
