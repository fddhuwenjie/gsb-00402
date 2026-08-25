import logging
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.entities.models import AnalysisTask, AnalysisResult, TaskStatus

logger = logging.getLogger(__name__)


class AnalysisRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_all(self, page: int = 1, page_size: int = 20) -> tuple[list[AnalysisTask], int]:
        count_stmt = select(func.count()).select_from(AnalysisTask)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(AnalysisTask)
            .options(
                selectinload(AnalysisTask.creator),
                selectinload(AnalysisTask.signature_files),
                selectinload(AnalysisTask.result),
            )
            .order_by(AnalysisTask.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def find_by_id(self, task_id: int) -> AnalysisTask | None:
        stmt = (
            select(AnalysisTask)
            .options(
                selectinload(AnalysisTask.creator),
                selectinload(AnalysisTask.signature_files),
                selectinload(AnalysisTask.result),
            )
            .where(AnalysisTask.id == task_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, task: AnalysisTask) -> AnalysisTask:
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        logger.info("Created analysis task: %s (id=%d)", task.name, task.id)
        return task

    async def update_status(self, task_id: int, status: TaskStatus, error_message: str = None):
        task = await self.find_by_id(task_id)
        if task:
            task.status = status
            if error_message:
                task.error_message = error_message
            await self.db.flush()

    async def save_result(self, result: AnalysisResult) -> AnalysisResult:
        self.db.add(result)
        await self.db.flush()
        await self.db.refresh(result)
        return result

    async def delete_by_id(self, task_id: int) -> bool:
        stmt = delete(AnalysisTask).where(AnalysisTask.id == task_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def count_by_status(self) -> dict[str, int]:
        stmt = (
            select(AnalysisTask.status, func.count())
            .group_by(AnalysisTask.status)
        )
        result = await self.db.execute(stmt)
        return {str(row[0].value): row[1] for row in result.all()}

    async def count_total(self) -> int:
        stmt = select(func.count()).select_from(AnalysisTask)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def risk_distribution(self) -> dict[str, int]:
        stmt = (
            select(AnalysisResult.risk_level, func.count())
            .group_by(AnalysisResult.risk_level)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def language_distribution(self) -> dict[str, int]:
        stmt = (
            select(AnalysisTask.language, func.count())
            .group_by(AnalysisTask.language)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
