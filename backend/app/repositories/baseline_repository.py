import logging
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.entities.models import Baseline, DiffReport

logger = logging.getLogger(__name__)


class BaselineRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_all(
        self, page: int = 1, page_size: int = 20, owner_id: int | None = None
    ) -> tuple[list[Baseline], int]:
        count_stmt = select(func.count()).select_from(Baseline)
        stmt = (
            select(Baseline)
            .options(selectinload(Baseline.creator))
            .order_by(Baseline.created_at.desc())
        )
        if owner_id is not None:
            count_stmt = count_stmt.where(Baseline.created_by == owner_id)
            stmt = stmt.where(Baseline.created_by == owner_id)

        total = (await self.db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def find_by_id(self, baseline_id: int) -> Baseline | None:
        stmt = (
            select(Baseline)
            .options(selectinload(Baseline.creator))
            .where(Baseline.id == baseline_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, baseline: Baseline) -> Baseline:
        self.db.add(baseline)
        await self.db.flush()
        await self.db.refresh(baseline)
        logger.info("Created baseline: %s (id=%d)", baseline.name, baseline.id)
        return baseline

    async def delete_by_id(self, baseline_id: int) -> bool:
        stmt = delete(Baseline).where(Baseline.id == baseline_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def save_diff(self, diff: DiffReport) -> DiffReport:
        self.db.add(diff)
        await self.db.flush()
        await self.db.refresh(diff)
        return diff

    async def find_diff_by_id(self, diff_id: int) -> DiffReport | None:
        stmt = (
            select(DiffReport)
            .options(
                selectinload(DiffReport.baseline),
                selectinload(DiffReport.task),
                selectinload(DiffReport.creator),
            )
            .where(DiffReport.id == diff_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_diffs_by_task(
        self, task_id: int, owner_id: int | None = None
    ) -> list[DiffReport]:
        stmt = (
            select(DiffReport)
            .options(
                selectinload(DiffReport.baseline),
                selectinload(DiffReport.task),
                selectinload(DiffReport.creator),
            )
            .where(DiffReport.task_id == task_id)
            .order_by(DiffReport.created_at.desc())
        )
        if owner_id is not None:
            stmt = stmt.join(Baseline, DiffReport.baseline_id == Baseline.id).where(
                Baseline.created_by == owner_id
            )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_diff_by_baseline_and_task(
        self, baseline_id: int, task_id: int
    ) -> DiffReport | None:
        stmt = (
            select(DiffReport)
            .options(
                selectinload(DiffReport.baseline),
                selectinload(DiffReport.task),
                selectinload(DiffReport.creator),
            )
            .where(DiffReport.baseline_id == baseline_id, DiffReport.task_id == task_id)
            .order_by(DiffReport.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
