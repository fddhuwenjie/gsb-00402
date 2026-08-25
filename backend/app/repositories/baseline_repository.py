import logging
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.entities.models import Baseline, DiffReport

logger = logging.getLogger(__name__)


class BaselineRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_all(self, page: int = 1, page_size: int = 20) -> tuple[list[Baseline], int]:
        count_stmt = select(func.count()).select_from(Baseline)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(Baseline)
            .options(selectinload(Baseline.task), selectinload(Baseline.creator))
            .order_by(Baseline.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def find_by_id(self, baseline_id: int) -> Baseline | None:
        stmt = (
            select(Baseline)
            .options(selectinload(Baseline.task), selectinload(Baseline.creator))
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


class DiffReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_baseline(self, baseline_id: int) -> list[DiffReport]:
        stmt = (
            select(DiffReport)
            .options(selectinload(DiffReport.task), selectinload(DiffReport.creator), selectinload(DiffReport.baseline))
            .where(DiffReport.baseline_id == baseline_id)
            .order_by(DiffReport.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_id(self, diff_id: int) -> DiffReport | None:
        stmt = (
            select(DiffReport)
            .options(selectinload(DiffReport.task), selectinload(DiffReport.creator), selectinload(DiffReport.baseline))
            .where(DiffReport.id == diff_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_pair(self, baseline_id: int, task_id: int) -> DiffReport | None:
        stmt = select(DiffReport).where(
            DiffReport.baseline_id == baseline_id,
            DiffReport.task_id == task_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, report: DiffReport) -> DiffReport:
        self.db.add(report)
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def delete(self, report: DiffReport):
        await self.db.delete(report)
        await self.db.flush()
