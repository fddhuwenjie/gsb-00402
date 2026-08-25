"""
Baseline and diff report service.
Saves analysis baselines and computes crypto asset diffs against later analyses.
"""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.baseline_differ import BaselineDiffer
from app.entities.models import Baseline, DiffReport, TaskStatus
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.baseline_repository import BaselineRepository, DiffReportRepository
from app.schemas.baseline import (
    BaselineCreateRequest,
    BaselineDTO,
    BaselineDetailDTO,
    DiffReportDTO,
    DiffReportDetailDTO,
)
from app.schemas.common import PageResponse

logger = logging.getLogger(__name__)


class BaselineService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.baseline_repo = BaselineRepository(db)
        self.diff_repo = DiffReportRepository(db)
        self.analysis_repo = AnalysisRepository(db)

    async def create_baseline(self, req: BaselineCreateRequest, user_id: int) -> BaselineDTO:
        task = await self.analysis_repo.find_by_id(req.task_id)
        if not task:
            raise ValueError(f"Analysis task not found: {req.task_id}")
        if task.status != TaskStatus.COMPLETED or not task.result:
            raise ValueError("只有已完成的分析任务才能保存为基线")

        report = json.loads(task.result.report_json)
        assets = BaselineDiffer.extract_assets(report)

        baseline = Baseline(
            name=req.name,
            task_id=task.id,
            language=task.language,
            code_path=task.code_path,
            snapshot_json=json.dumps(assets, ensure_ascii=False),
            asset_count=len(assets),
            created_by=user_id,
        )
        baseline = await self.baseline_repo.create(baseline)
        await self.db.commit()
        logger.info("Baseline created from task %d: %d assets", task.id, len(assets))

        baseline = await self.baseline_repo.find_by_id(baseline.id)
        return self._build_dto(baseline)

    async def list_baselines(self, page: int = 1, page_size: int = 20) -> PageResponse[BaselineDTO]:
        items, total = await self.baseline_repo.find_all(page, page_size)
        total_pages = (total + page_size - 1) // page_size
        return PageResponse(
            items=[self._build_dto(b) for b in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_baseline_detail(self, baseline_id: int) -> BaselineDetailDTO:
        baseline = await self.baseline_repo.find_by_id(baseline_id)
        if not baseline:
            raise ValueError(f"Baseline not found: {baseline_id}")
        assets = list(json.loads(baseline.snapshot_json).values())
        return BaselineDetailDTO(baseline=self._build_dto(baseline), assets=assets)

    async def delete_baseline(self, baseline_id: int) -> bool:
        deleted = await self.baseline_repo.delete_by_id(baseline_id)
        if deleted:
            await self.db.commit()
        return deleted

    async def generate_diff(self, baseline_id: int, task_id: int, user_id: int) -> DiffReportDetailDTO:
        baseline = await self.baseline_repo.find_by_id(baseline_id)
        if not baseline:
            raise ValueError(f"Baseline not found: {baseline_id}")

        task = await self.analysis_repo.find_by_id(task_id)
        if not task:
            raise ValueError(f"Analysis task not found: {task_id}")
        if task.status != TaskStatus.COMPLETED or not task.result:
            raise ValueError("只有已完成的分析任务才能生成差异报告")
        if task.code_path != baseline.code_path:
            raise ValueError(
                f"代码路径与基线不一致（基线: {baseline.code_path}，当前: {task.code_path}），不允许跨项目生成差异报告"
            )
        if task.language != baseline.language:
            raise ValueError(
                f"代码语言与基线不一致（基线: {baseline.language}，当前: {task.language}），不允许生成差异报告"
            )

        baseline_assets = json.loads(baseline.snapshot_json)
        current_assets = BaselineDiffer.extract_assets(json.loads(task.result.report_json))
        diff = BaselineDiffer.compute(baseline_assets, current_assets)

        # 同一基线 + 任务只保留最新的一份差异报告
        existing = await self.diff_repo.find_by_pair(baseline_id, task_id)
        if existing:
            await self.diff_repo.delete(existing)

        report = DiffReport(
            baseline_id=baseline_id,
            task_id=task_id,
            diff_json=json.dumps(diff, ensure_ascii=False),
            added_count=diff["summary"]["added"],
            removed_count=diff["summary"]["removed"],
            changed_count=diff["summary"]["changed"],
            created_by=user_id,
        )
        report = await self.diff_repo.save(report)
        await self.db.commit()
        logger.info(
            "Diff report generated: baseline=%d task=%d added=%d removed=%d changed=%d",
            baseline_id, task_id, report.added_count, report.removed_count, report.changed_count,
        )

        report = await self.diff_repo.find_by_id(report.id)
        return self._build_diff_detail(report)

    async def list_diffs(self, baseline_id: int) -> list[DiffReportDTO]:
        baseline = await self.baseline_repo.find_by_id(baseline_id)
        if not baseline:
            raise ValueError(f"Baseline not found: {baseline_id}")
        reports = await self.diff_repo.find_by_baseline(baseline_id)
        return [self._build_diff_dto(r) for r in reports]

    async def get_diff_detail(self, diff_id: int) -> DiffReportDetailDTO:
        report = await self.diff_repo.find_by_id(diff_id)
        if not report:
            raise ValueError(f"Diff report not found: {diff_id}")
        return self._build_diff_detail(report)

    def _build_dto(self, baseline: Baseline) -> BaselineDTO:
        return BaselineDTO(
            id=baseline.id,
            name=baseline.name,
            task_id=baseline.task_id,
            task_name=baseline.task.name if baseline.task else "",
            language=baseline.language,
            code_path=baseline.code_path,
            asset_count=baseline.asset_count,
            created_by=baseline.created_by,
            creator_name=baseline.creator.username if baseline.creator else "",
            created_at=baseline.created_at,
        )

    def _build_diff_dto(self, report: DiffReport) -> DiffReportDTO:
        return DiffReportDTO(
            id=report.id,
            baseline_id=report.baseline_id,
            baseline_name=report.baseline.name if report.baseline else "",
            task_id=report.task_id,
            task_name=report.task.name if report.task else "",
            added_count=report.added_count,
            removed_count=report.removed_count,
            changed_count=report.changed_count,
            created_by=report.created_by,
            creator_name=report.creator.username if report.creator else "",
            created_at=report.created_at,
        )

    def _build_diff_detail(self, report: DiffReport) -> DiffReportDetailDTO:
        return DiffReportDetailDTO(
            report=self._build_diff_dto(report),
            diff=json.loads(report.diff_json),
        )
