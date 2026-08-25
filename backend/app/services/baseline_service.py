"""
Baseline & diff service.

Saves an analysis snapshot as a baseline and computes structured diffs between a
baseline and a later analysis task. Enforces project consistency (same code path
and language) so diffs only compare comparable projects.
"""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.baseline_diff import BaselineDiffEngine
from app.entities.models import AnalysisBaseline, DiffReport, TaskStatus
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.baseline_repository import BaselineRepository
from app.schemas.baseline import (
    BaselineCreateRequest,
    DiffGenerateRequest,
    BaselineDTO,
    DiffReportDTO,
    DiffReportSummaryDTO,
)
from app.schemas.common import PageResponse

logger = logging.getLogger(__name__)


class BaselineService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BaselineRepository(db)
        self.analysis_repo = AnalysisRepository(db)
        self.engine = BaselineDiffEngine()

    async def create_baseline(self, req: BaselineCreateRequest, user_id: int) -> BaselineDTO:
        task = await self.analysis_repo.find_by_id(req.task_id)
        if not task:
            raise ValueError(f"分析任务不存在: {req.task_id}")
        if task.status != TaskStatus.COMPLETED:
            raise ValueError("只能为已完成的分析任务创建基线")
        if not task.result:
            raise ValueError("该分析任务没有可用的报告结果")

        baseline = AnalysisBaseline(
            name=req.name,
            description=req.description,
            task_id=task.id,
            language=task.language,
            code_path=task.code_path,
            project_key=task.project_key,
            report_json=task.result.report_json,
            created_by=user_id,
        )
        baseline = await self.repo.create(baseline)
        await self.db.commit()

        baseline = await self.repo.find_by_id(baseline.id)
        return self._to_baseline_dto(baseline)

    async def list_baselines(self, page: int = 1, page_size: int = 20) -> PageResponse[BaselineDTO]:
        items, total = await self.repo.find_all(page, page_size)
        total_pages = (total + page_size - 1) // page_size
        return PageResponse(
            items=[self._to_baseline_dto(b) for b in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_baseline(self, baseline_id: int) -> BaselineDTO:
        baseline = await self.repo.find_by_id(baseline_id)
        if not baseline:
            raise ValueError(f"基线不存在: {baseline_id}")
        return self._to_baseline_dto(baseline)

    async def delete_baseline(self, baseline_id: int) -> bool:
        return await self.repo.delete_by_id(baseline_id)

    async def generate_diff(self, baseline_id: int, req: DiffGenerateRequest, user_id: int) -> DiffReportDTO:
        baseline = await self.repo.find_by_id(baseline_id)
        if not baseline:
            raise ValueError(f"基线不存在: {baseline_id}")

        task = await self.analysis_repo.find_by_id(req.task_id)
        if not task:
            raise ValueError(f"分析任务不存在: {req.task_id}")
        if task.status != TaskStatus.COMPLETED:
            raise ValueError("只能与已完成的分析任务比较")
        if not task.result:
            raise ValueError("该分析任务没有可用的报告结果")

        # Consistency check: only compare analyses of the same project. Identity
        # is the stable project_key, not the code path — uploaded projects get a
        # fresh temp directory on every upload, so paths would never match.
        if task.project_key != baseline.project_key:
            raise ValueError("所选分析任务与基线不属于同一项目，无法比较")
        if task.language != baseline.language:
            raise ValueError("所选分析任务的语言与基线不一致，无法比较")

        baseline_report = json.loads(baseline.report_json)
        new_report = json.loads(task.result.report_json)
        diff = self.engine.compute(baseline_report, new_report)

        # Reuse (overwrite) any prior diff for the same baseline+task pair.
        report = await self.repo.find_existing_diff(baseline_id, task.id)
        if report is None:
            report = DiffReport(baseline_id=baseline_id, task_id=task.id, created_by=user_id)

        report.diff_json = json.dumps(diff, ensure_ascii=False)
        report.total_added = diff["summary"]["total_added"]
        report.total_removed = diff["summary"]["total_removed"]
        report.total_changed = diff["summary"]["total_changed"]
        report = await self.repo.save_diff(report)
        await self.db.commit()

        report = await self.repo.find_diff_by_id(report.id)
        logger.info(
            "Diff generated: baseline=%d task=%d added=%d removed=%d changed=%d",
            baseline_id, task.id, report.total_added, report.total_removed, report.total_changed,
        )
        return self._to_diff_dto(report)

    async def get_diff(self, diff_id: int) -> DiffReportDTO:
        report = await self.repo.find_diff_by_id(diff_id)
        if not report:
            raise ValueError(f"差异报告不存在: {diff_id}")
        return self._to_diff_dto(report)

    async def list_diffs(self, baseline_id: int) -> list[DiffReportSummaryDTO]:
        baseline = await self.repo.find_by_id(baseline_id)
        if not baseline:
            raise ValueError(f"基线不存在: {baseline_id}")
        reports = await self.repo.find_diffs_by_baseline(baseline_id)
        return [
            DiffReportSummaryDTO(
                id=r.id,
                baseline_id=r.baseline_id,
                baseline_name=r.baseline.name if r.baseline else "",
                task_id=r.task_id,
                task_name=r.task.name if r.task else "",
                total_added=r.total_added,
                total_removed=r.total_removed,
                total_changed=r.total_changed,
                created_at=r.created_at,
            )
            for r in reports
        ]

    def _to_baseline_dto(self, b: AnalysisBaseline) -> BaselineDTO:
        return BaselineDTO(
            id=b.id,
            name=b.name,
            description=b.description or "",
            task_id=b.task_id,
            task_name=b.task.name if b.task else "",
            language=b.language,
            code_path=b.code_path,
            project_key=b.project_key,
            created_by=b.created_by,
            creator_name=b.creator.username if b.creator else "",
            created_at=b.created_at,
        )

    def _to_diff_dto(self, r: DiffReport) -> DiffReportDTO:
        return DiffReportDTO(
            id=r.id,
            baseline_id=r.baseline_id,
            baseline_name=r.baseline.name if r.baseline else "",
            task_id=r.task_id,
            task_name=r.task.name if r.task else "",
            total_added=r.total_added,
            total_removed=r.total_removed,
            total_changed=r.total_changed,
            diff=json.loads(r.diff_json),
            created_by=r.created_by,
            creator_name=r.creator.username if r.creator else "",
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
