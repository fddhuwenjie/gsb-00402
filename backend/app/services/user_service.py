import logging

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.models import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserDTO
from app.schemas.common import PageResponse
from app.schemas.user import UserCreateRequest, UserUpdateRequest

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def list_users(self, page: int = 1, page_size: int = 20) -> PageResponse[UserDTO]:
        items, total = await self.repo.find_all(page, page_size)
        total_pages = (total + page_size - 1) // page_size
        return PageResponse(
            items=[
                UserDTO(id=u.id, username=u.username, role=u.role.value, created_at=u.created_at)
                for u in items
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def create_user(self, req: UserCreateRequest) -> UserDTO:
        existing = await self.repo.find_by_username(req.username)
        if existing:
            raise ValueError(f"Username '{req.username}' already exists")

        hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
        role = UserRole(req.role) if req.role in [r.value for r in UserRole] else UserRole.USER
        user = User(username=req.username, password_hash=hashed, role=role)
        user = await self.repo.create(user)
        logger.info("Admin created user: %s role=%s", user.username, role.value)
        return UserDTO(id=user.id, username=user.username, role=user.role.value, created_at=user.created_at)

    async def update_user(self, user_id: int, req: UserUpdateRequest) -> UserDTO:
        user = await self.repo.find_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if req.role is not None:
            role = UserRole(req.role) if req.role in [r.value for r in UserRole] else user.role
            await self.repo.update_role(user_id, role)
            logger.info("Updated role for user %s to %s", user.username, role.value)

        if req.password is not None and req.password.strip():
            if len(req.password) < 6:
                raise ValueError("Password must be at least 6 characters")
            hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
            await self.repo.update_password(user_id, hashed)
            logger.info("Updated password for user %s", user.username)

        user = await self.repo.find_by_id(user_id)
        return UserDTO(id=user.id, username=user.username, role=user.role.value, created_at=user.created_at)

    async def delete_user(self, user_id: int, current_user_id: int) -> bool:
        if user_id == current_user_id:
            raise ValueError("Cannot delete yourself")
        user = await self.repo.find_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if user.username == "admin":
            raise ValueError("Cannot delete the default admin account")
        deleted = await self.repo.delete_by_id(user_id)
        if deleted:
            logger.info("Deleted user: id=%d username=%s", user_id, user.username)
        return deleted
