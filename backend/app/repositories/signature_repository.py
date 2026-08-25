import logging
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.models import SignatureFile

logger = logging.getLogger(__name__)


class SignatureRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_all(self, page: int = 1, page_size: int = 20) -> tuple[list[SignatureFile], int]:
        count_stmt = select(func.count()).select_from(SignatureFile)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(SignatureFile)
            .order_by(SignatureFile.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def find_by_id(self, sig_id: int) -> SignatureFile | None:
        stmt = select(SignatureFile).where(SignatureFile.id == sig_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_ids(self, ids: list[int]) -> list[SignatureFile]:
        stmt = select(SignatureFile).where(SignatureFile.id.in_(ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, sig: SignatureFile) -> SignatureFile:
        self.db.add(sig)
        await self.db.flush()
        await self.db.refresh(sig)
        logger.info("Created signature file: %s (id=%d)", sig.name, sig.id)
        return sig

    async def delete_by_id(self, sig_id: int) -> bool:
        stmt = delete(SignatureFile).where(SignatureFile.id == sig_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def count(self) -> int:
        stmt = select(func.count()).select_from(SignatureFile)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def total_functions(self) -> int:
        stmt = select(func.sum(SignatureFile.function_count))
        result = await self.db.execute(stmt)
        return result.scalar() or 0
