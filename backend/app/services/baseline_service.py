"""
Business logic for analysis baselines and differential reports.

Access control:
  * Every baseline / diff / source-analysis can only be accessed or modified by
    its owning user. This restriction applies to all users, including
    administrators — resource ownership is never bypassed.
  * A diff may only be generated when the baseline and the current analysis
    belong to the *same project*, identified by a stable ``project_key`` and
    matching language. Upload-based analyses must supply an explicit
    ``project_key`` so that repeated uploads of the same project can be
    compared.
"""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.deps import CurrentUser
from app.core.diff_engine import DiffEngine
from app.entities.models import Baseline, DiffReport, AnalysisTask, TaskStatus
from app.exceptions.handlers import ForbiddenException, NotFoundException
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.baseline_repository import BaselineRepository
from app.schemas.baseline import (
    BaselineCreateRequest,
    BaselineDTO,
    BaselineDetailDTO,
    DiffDetailDTO,
    DiffReportDTO,
)
from app.schemas.common import PageResponse

logger = logging.getLogger(__name__)


class BaselineService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BaselineRepository(db)
        self.analysis_repo = AnalysisRepository(db)
        self.diff_engine = DiffEngine()

    # ------------------------------------------------------------------
    # Baselines
    # ------------------------------------------------------------------

    async def create_baseline(
        self, req: BaselineCreateRequest, current_user: CurrentUser
    ) -> BaselineDetailDTO:
        task = await self.analysis_repo.find_by_id(req.task_id)
        if not task:
            raise NotFoundException(f"Analysis task not found: {req.task_id}")

        self._ensure_owner(task.created_by, current_user, "来源分析任务")

        if task.status != TaskStatus.COMPLETED or not task.result:
            raise ValueError("只能基于已完成且有结果的分析任务创建基线")

        report = json.loads(task.result.report_json)
        assets = self.diff_engine.extract_assets(report)

        baseline = Baseline(
            name=req.name,
            description=req.description,
            source_task_id=task.id,
            language=task.language,
            code_path=task.code_path,
            project_key=task.project_key or "",
            report_json=task.result.report_json,
            asset_count=len(assets),
            created_by=current_user.id,
        )
        baseline = await self.repo.create(baseline)
        await self.db.commit()
        await self.db.refresh(baseline, ["creator"])

        logger.info(
            "Baseline created by user %d: %s (id=%d, assets=%d)",
            current_user.id, baseline.name, baseline.id, baseline.asset_count,
        )
        return self._build_detail_dto(baseline)

    async def list_baselines(
        self, current_user: CurrentUser, page: int = 1, page_size: int = 20
    ) -> PageResponse[BaselineDTO]:
        items, total = await self.repo.find_all(page, page_size, owner_id=current_user.id)
        total_pages = (total + page_size - 1) // page_size
        dtos = [self._build_dto(b) for b in items]
        return PageResponse(
            items=dtos, total=total, page=page, page_size=page_size, total_pages=total_pages,
        )

    async def get_baseline(
        self, baseline_id: int, current_user: CurrentUser
    ) -> BaselineDetailDTO:
        baseline = await self.repo.find_by_id(baseline_id)
        if not baseline:
            raise NotFoundException(f"Baseline not found: {baseline_id}")
        self._ensure_owner(baseline.created_by, current_user, "基线")
        return self._build_detail_dto(baseline)

    async def delete_baseline(
        self, baseline_id: int, current_user: CurrentUser
    ) -> bool:
        baseline = await self.repo.find_by_id(baseline_id)
        if not baseline:
            return False
        self._ensure_owner(baseline.created_by, current_user, "基线")
        deleted = await self.repo.delete_by_id(baseline_id)
        if deleted:
            logger.info(
                "Baseline deleted by user %d: id=%d", current_user.id, baseline_id,
            )
        return deleted

    # ------------------------------------------------------------------
    # Diffs
    # ------------------------------------------------------------------

    async def create_diff(
        self, baseline_id: int, task_id: int, current_user: CurrentUser
    ) -> DiffDetailDTO:
        baseline, task = await self._load_and_authorize_diff_pair(
            baseline_id, task_id, current_user
        )

        baseline_report = json.loads(baseline.report_json)
        current_report = json.loads(task.result.report_json)

        diff = self._build_diff_payload(baseline, task, baseline_report, current_report)

        diff_record = await self._persist_diff(baseline_id, task_id, diff, current_user.id)

        logger.info(
            "Diff created by user %d: baseline=%d, task=%d, added=%d, removed=%d, changed=%d",
            current_user.id, baseline_id, task_id,
            diff_record.added_count, diff_record.removed_count, diff_record.changed_count,
        )
        return self._build_diff_detail_dto(diff_record)

    async def get_diff(
        self, diff_id: int, current_user: CurrentUser
    ) -> DiffDetailDTO:
        diff = await self.repo.find_diff_by_id(diff_id)
        if not diff:
            raise NotFoundException(f"Diff report not found: {diff_id}")
        self._ensure_owner(diff.created_by, current_user, "差异报告")
        return self._build_diff_detail_dto(diff)

    async def list_diffs_by_task(
        self, task_id: int, current_user: CurrentUser
    ) -> list[DiffReportDTO]:
        task = await self.analysis_repo.find_by_id(task_id)
        if not task:
            raise NotFoundException(f"Analysis task not found: {task_id}")
        self._ensure_owner(task.created_by, current_user, "分析任务")

        diffs = await self.repo.find_diffs_by_task(task_id, owner_id=current_user.id)
        return [self._build_diff_dto(d) for d in diffs]

    async def maybe_create_diff_for_task(
        self,
        task: AnalysisTask,
        baseline_id: int | None,
        current_user: CurrentUser,
    ) -> DiffReport | None:
        """
        Internal helper invoked by the analysis flow after a task completes.

        Unlike the previous behaviour, any failure (missing baseline, ownership
        mismatch, cross-project mismatch) raises a clear exception instead of
        being silently swallowed so the caller can surface it to the user.
        """
        if not baseline_id:
            return None
        if not task.result:
            raise ValueError("分析任务尚未产生结果，无法生成基线差异")

        baseline = await self.repo.find_by_id(baseline_id)
        if not baseline:
            raise NotFoundException(f"Baseline not found: {baseline_id}")

        self._ensure_owner(baseline.created_by, current_user, "基线")
        self._ensure_owner(task.created_by, current_user, "当前分析任务")
        self._ensure_same_project(baseline, task)

        baseline_report = json.loads(baseline.report_json)
        current_report = json.loads(task.result.report_json)
        diff = self._build_diff_payload(baseline, task, baseline_report, current_report)

        diff_record = DiffReport(
            baseline_id=baseline_id,
            task_id=task.id,
            diff_json=json.dumps(diff, ensure_ascii=False),
            added_count=diff["summary"]["added"],
            removed_count=diff["summary"]["removed"],
            changed_count=diff["summary"]["changed"],
            unchanged_count=diff["summary"]["unchanged"],
            risk_level=diff["summary"]["risk_level"],
            created_by=current_user.id,
        )
        return await self.repo.save_diff(diff_record)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_and_authorize_diff_pair(
        self,
        baseline_id: int,
        task_id: int,
        current_user: CurrentUser,
    ) -> tuple[Baseline, AnalysisTask]:
        baseline = await self.repo.find_by_id(baseline_id)
        if not baseline:
            raise NotFoundException(f"Baseline not found: {baseline_id}")

        task = await self.analysis_repo.find_by_id(task_id)
        if not task:
            raise NotFoundException(f"Analysis task not found: {task_id}")

        self._ensure_owner(baseline.created_by, current_user, "基线")
        self._ensure_owner(task.created_by, current_user, "当前分析任务")

        if task.status != TaskStatus.COMPLETED or not task.result:
            raise ValueError("只能对比已完成且有结果的分析任务")

        self._ensure_same_project(baseline, task)
        return baseline, task

    def _build_diff_payload(
        self,
        baseline: Baseline,
        task: AnalysisTask,
        baseline_report: dict,
        current_report: dict,
    ) -> dict:
        return self.diff_engine.compute_diff(
            baseline_report,
            current_report,
            baseline_meta={
                "id": baseline.id,
                "name": baseline.name,
                "source_task_id": baseline.source_task_id,
                "created_at": baseline.created_at.isoformat() if baseline.created_at else None,
            },
            current_meta={
                "task_id": task.id,
                "name": task.name,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            },
        )

    async def _persist_diff(
        self,
        baseline_id: int,
        task_id: int,
        diff: dict,
        user_id: int,
    ) -> DiffReport:
        existing = await self.repo.find_diff_by_baseline_and_task(baseline_id, task_id)
        if existing:
            existing.diff_json = json.dumps(diff, ensure_ascii=False)
            existing.added_count = diff["summary"]["added"]
            existing.removed_count = diff["summary"]["removed"]
            existing.changed_count = diff["summary"]["changed"]
            existing.unchanged_count = diff["summary"]["unchanged"]
            existing.risk_level = diff["summary"]["risk_level"]
            await self.db.flush()
            diff_record = existing
        else:
            diff_record = DiffReport(
                baseline_id=baseline_id,
                task_id=task_id,
                diff_json=json.dumps(diff, ensure_ascii=False),
                added_count=diff["summary"]["added"],
                removed_count=diff["summary"]["removed"],
                changed_count=diff["summary"]["changed"],
                unchanged_count=diff["summary"]["unchanged"],
                risk_level=diff["summary"]["risk_level"],
                created_by=user_id,
            )
            diff_record = await self.repo.save_diff(diff_record)

        await self.db.commit()
        await self.db.refresh(diff_record, ["baseline", "task", "creator"])
        return diff_record

    @staticmethod
    def _ensure_owner(
        owner_id: int, current_user: CurrentUser, resource: str
    ) -> None:
        if owner_id != current_user.id:
            raise ForbiddenException(f"无权访问或操作此{resource}")

    @staticmethod
    def _ensure_same_project(baseline: Baseline, task: AnalysisTask) -> None:
        if baseline.language != task.language:
            raise ForbiddenException(
                f"基线与当前分析语言不一致，无法对比（基线: {baseline.language}, 当前: {task.language}）"
            )

        base_key = (baseline.project_key or "").strip()
        task_key = (task.project_key or "").strip()

        if not base_key or not task_key:
            raise ForbiddenException(
                "基线或当前分析缺少项目标识（project_key），无法判定是否属于同一项目"
            )

        if base_key != task_key:
            raise ForbiddenException(
                f"基线与当前分析不属于同一项目，无法生成差异（项目标识: {base_key} ≠ {task_key}）"
            )

    # ------------------------------------------------------------------
    # DTO builders
    # ------------------------------------------------------------------

    def _build_dto(self, baseline: Baseline) -> BaselineDTO:
        source_task_name = ""
        if baseline.source_task_id:
            source_task_name = f"Task #{baseline.source_task_id}"
        return BaselineDTO(
            id=baseline.id,
            name=baseline.name,
            description=baseline.description or "",
            source_task_id=baseline.source_task_id,
            source_task_name=source_task_name,
            language=baseline.language,
            code_path=baseline.code_path,
            project_key=baseline.project_key or "",
            asset_count=baseline.asset_count,
            created_by=baseline.created_by,
            creator_name=baseline.creator.username if baseline.creator else "",
            created_at=baseline.created_at,
        )

    def _build_detail_dto(self, baseline: Baseline) -> BaselineDetailDTO:
        dto = self._build_dto(baseline)
        return BaselineDetailDTO(
            **dto.model_dump(),
            report=json.loads(baseline.report_json),
        )

    def _build_diff_dto(self, diff: DiffReport) -> DiffReportDTO:
        return DiffReportDTO(
            id=diff.id,
            baseline_id=diff.baseline_id,
            baseline_name=diff.baseline.name if diff.baseline else "",
            task_id=diff.task_id,
            task_name=diff.task.name if diff.task else "",
            added_count=diff.added_count,
            removed_count=diff.removed_count,
            changed_count=diff.changed_count,
            unchanged_count=diff.unchanged_count,
            risk_level=diff.risk_level,
            created_by=diff.created_by,
            creator_name=diff.creator.username if diff.creator else "",
            created_at=diff.created_at,
        )

    def _build_diff_detail_dto(self, diff: DiffReport) -> DiffDetailDTO:
        dto = self._build_diff_dto(diff)
        return DiffDetailDTO(
            **dto.model_dump(),
            diff=json.loads(diff.diff_json),
        )
