import logging
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.models import User, UserRole

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_all(self, page: int = 1, page_size: int = 20) -> tuple[list[User], int]:
        count_stmt = select(func.count()).select_from(User)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        logger.info("Created user: %s (id=%d)", user.username, user.id)
        return user

    async def update_role(self, user_id: int, role: UserRole) -> bool:
        stmt = update(User).where(User.id == user_id).values(role=role)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def update_password(self, user_id: int, password_hash: str) -> bool:
        stmt = update(User).where(User.id == user_id).values(password_hash=password_hash)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_id(self, user_id: int) -> bool:
        stmt = delete(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def count(self) -> int:
        stmt = select(func.count()).select_from(User)
        result = await self.db.execute(stmt)
        return result.scalar() or 0
