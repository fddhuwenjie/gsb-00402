import logging

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.entities.models import AnalysisBaseline, DiffReport

logger = logging.getLogger(__name__)


class BaselineRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- baselines ---------------------------------------------------------

    async def create(self, baseline: AnalysisBaseline) -> AnalysisBaseline:
        self.db.add(baseline)
        await self.db.flush()
        await self.db.refresh(baseline)
        logger.info("Created baseline: %s (id=%d)", baseline.name, baseline.id)
        return baseline

    async def find_all(self, page: int = 1, page_size: int = 20) -> tuple[list[AnalysisBaseline], int]:
        total = (await self.db.execute(
            select(func.count()).select_from(AnalysisBaseline)
        )).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(AnalysisBaseline)
            .options(
                selectinload(AnalysisBaseline.task),
                selectinload(AnalysisBaseline.creator),
            )
            .order_by(AnalysisBaseline.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def find_by_id(self, baseline_id: int) -> AnalysisBaseline | None:
        stmt = (
            select(AnalysisBaseline)
            .options(
                selectinload(AnalysisBaseline.task),
                selectinload(AnalysisBaseline.creator),
            )
            .where(AnalysisBaseline.id == baseline_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def delete_by_id(self, baseline_id: int) -> bool:
        result = await self.db.execute(
            delete(AnalysisBaseline).where(AnalysisBaseline.id == baseline_id)
        )
        return result.rowcount > 0

    # --- diff reports ------------------------------------------------------

    async def save_diff(self, report: DiffReport) -> DiffReport:
        self.db.add(report)
        await self.db.flush()
        await self.db.refresh(report)
        return report

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
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_existing_diff(self, baseline_id: int, task_id: int) -> DiffReport | None:
        """Locate a prior diff for the same baseline+task so it can be replaced."""
        stmt = select(DiffReport).where(
            DiffReport.baseline_id == baseline_id,
            DiffReport.task_id == task_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_diffs_by_baseline(self, baseline_id: int) -> list[DiffReport]:
        stmt = (
            select(DiffReport)
            .options(
                selectinload(DiffReport.baseline),
                selectinload(DiffReport.task),
                selectinload(DiffReport.creator),
            )
            .where(DiffReport.baseline_id == baseline_id)
            .order_by(DiffReport.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())
