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
        self, page: int = 1, page_size: int = 20, created_by: int | None = None
    ) -> tuple[list[Baseline], int]:
        filters = []
        if created_by is not None:
            filters.append(Baseline.created_by == created_by)

        count_stmt = select(func.count()).select_from(Baseline)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(Baseline)
            .options(
                selectinload(Baseline.task),
                selectinload(Baseline.creator),
            )
            .order_by(Baseline.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        if filters:
            stmt = stmt.where(*filters)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def find_by_id(self, baseline_id: int) -> Baseline | None:
        stmt = (
            select(Baseline)
            .options(
                selectinload(Baseline.task),
                selectinload(Baseline.creator),
            )
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

    async def find_all(
        self, page: int = 1, page_size: int = 20, created_by: int | None = None
    ) -> tuple[list[DiffReport], int]:
        filters = []
        if created_by is not None:
            filters.append(DiffReport.created_by == created_by)

        count_stmt = select(func.count()).select_from(DiffReport)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(DiffReport)
            .options(
                selectinload(DiffReport.baseline),
                selectinload(DiffReport.task),
                selectinload(DiffReport.creator),
            )
            .order_by(DiffReport.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        if filters:
            stmt = stmt.where(*filters)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def find_by_id(self, diff_id: int) -> DiffReport | None:
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

    async def create(self, diff_report: DiffReport) -> DiffReport:
        self.db.add(diff_report)
        await self.db.flush()
        await self.db.refresh(diff_report)
        logger.info("Created diff report: %s (id=%d)", diff_report.name, diff_report.id)
        return diff_report

    async def delete_by_id(self, diff_id: int) -> bool:
        stmt = delete(DiffReport).where(DiffReport.id == diff_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0
