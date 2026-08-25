"""
Baseline & diff service.

Persists crypto-asset snapshots of completed analyses as baselines and
generates added/removed/changed diff reports between a baseline and a
later analysis. All diffing logic lives in app.core.diff_engine.

Authorization model (mirrors the rest of the platform): admin users may
view and operate on every baseline/diff/analysis; regular users are
scoped to resources they created. Diffs may only compare a baseline with
an analysis of the same code project (identified by the analysis task's
normalized code path).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.diff_engine import DiffEngine
from app.entities.models import Baseline, DiffReport, AnalysisTask, TaskStatus
from app.exceptions.handlers import BusinessException, NotFoundException
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.baseline_repository import BaselineRepository, DiffReportRepository
from app.schemas.baseline import (
    BaselineCreateRequest,
    BaselineDTO,
    BaselineDetailDTO,
    DiffCreateRequest,
    DiffReportDTO,
    DiffReportDetailDTO,
)
from app.schemas.common import PageResponse

if TYPE_CHECKING:
    from app.controllers.deps import CurrentUser

logger = logging.getLogger(__name__)


class BaselineService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.baseline_repo = BaselineRepository(db)
        self.diff_repo = DiffReportRepository(db)
        self.analysis_repo = AnalysisRepository(db)
        self.engine = DiffEngine()

    # ---------------- authorization helpers ----------------

    @staticmethod
    def _is_admin(user: CurrentUser) -> bool:
        return user.role == "admin"

    @staticmethod
    def _assert_owner(resource, user: CurrentUser, label: str):
        """Regular users may only touch resources they created; admins see all."""
        if user.role != "admin" and getattr(resource, "created_by", None) != user.id:
            logger.warning(
                "User %d denied access to %s (owned by %s)",
                user.id, label, getattr(resource, "created_by", None),
            )
            raise BusinessException(f"无权访问该{label}", code=403)

    @staticmethod
    def _assert_task_owner(task: AnalysisTask | None, user: CurrentUser, label: str):
        if not task:
            raise NotFoundException(f"{label}任务不存在")
        if user.role != "admin" and task.created_by != user.id:
            logger.warning(
                "User %d denied access to analysis task %d (owned by %s)",
                user.id, task.id, task.created_by,
            )
            raise BusinessException("无权使用该分析任务", code=403)

    @staticmethod
    def _same_project(path_a: str, path_b: str) -> bool:
        """Project identity = normalized code path of the analysis task."""
        try:
            return Path(path_a).resolve() == Path(path_b).resolve()
        except (TypeError, ValueError):
            return path_a == path_b

    @staticmethod
    def _require_completed_result(task: AnalysisTask, label: str = "Analysis"):
        if task.status != TaskStatus.COMPLETED:
            raise BusinessException(f"{label}任务未完成（status={task.status.value}）", code=400)
        if not task.result:
            raise BusinessException(f"{label}任务没有分析结果", code=400)

    # ---------------- baselines ----------------

    async def create_baseline(self, req: BaselineCreateRequest, user: CurrentUser) -> BaselineDetailDTO:
        task = await self.analysis_repo.find_by_id(req.task_id)
        self._assert_task_owner(task, user, "基线来源")
        self._require_completed_result(task, "基线来源")

        report = json.loads(task.result.report_json)
        assets = self.engine.extract_assets(report)
        snapshot = {
            "assets": assets,
            "source_summary": report.get("summary", {}),
            "source_task_name": task.name,
            "source_code_path": task.code_path,
        }

        baseline = Baseline(
            name=req.name,
            description=req.description or "",
            task_id=task.id,
            language=task.language,
            snapshot_json=json.dumps(snapshot, ensure_ascii=False),
            total_assets=len(assets),
            risk_level=report.get("summary", {}).get("risk_level", "none"),
            created_by=user.id,
        )
        baseline = await self.baseline_repo.create(baseline)
        await self.db.commit()
        logger.info(
            "Baseline created by user %d: %s (id=%d, assets=%d)",
            user.id, baseline.name, baseline.id, len(assets),
        )

        self.db.expire_all()
        saved = await self.baseline_repo.find_by_id(baseline.id)
        return self._build_baseline_detail(saved)

    async def list_baselines(
        self, page: int = 1, page_size: int = 20, user: CurrentUser | None = None
    ) -> PageResponse[BaselineDTO]:
        scope_user = None if (user is None or self._is_admin(user)) else user.id
        items, total = await self.baseline_repo.find_all(page, page_size, created_by=scope_user)
        total_pages = (total + page_size - 1) // page_size
        return PageResponse(
            items=[self._build_baseline_dto(b) for b in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_baseline_detail(self, baseline_id: int, user: CurrentUser) -> BaselineDetailDTO:
        baseline = await self.baseline_repo.find_by_id(baseline_id)
        if not baseline:
            raise NotFoundException(f"基线不存在: {baseline_id}")
        self._assert_owner(baseline, user, "基线")
        return self._build_baseline_detail(baseline)

    async def delete_baseline(self, baseline_id: int) -> bool:
        deleted = await self.baseline_repo.delete_by_id(baseline_id)
        if deleted:
            logger.info("Deleted baseline: id=%d", baseline_id)
        return deleted

    # ---------------- diff reports ----------------

    async def create_diff(self, req: DiffCreateRequest, user: CurrentUser) -> DiffReportDetailDTO:
        baseline = await self.baseline_repo.find_by_id(req.baseline_id)
        if not baseline:
            raise NotFoundException(f"基线不存在: {req.baseline_id}")
        self._assert_owner(baseline, user, "基线")

        task = await self.analysis_repo.find_by_id(req.task_id)
        self._assert_task_owner(task, user, "当前对比")
        self._require_completed_result(task, "当前对比")

        baseline_task = baseline.task
        baseline_path = baseline_task.code_path if baseline_task else None
        if not baseline_path or not self._same_project(baseline_path, task.code_path):
            logger.warning(
                "Cross-project diff rejected: baseline=%d path=%s vs task=%d path=%s (user=%d)",
                baseline.id, baseline_path, task.id, task.code_path, user.id,
            )
            raise BusinessException(
                "基线来源分析与当前分析不属于同一个代码项目，无法生成差异报告", code=400
            )

        snapshot = json.loads(baseline.snapshot_json)
        baseline_assets = snapshot.get("assets", [])
        current_report = json.loads(task.result.report_json)
        current_assets = self.engine.extract_assets(current_report)

        diff = self.engine.compute_diff(
            baseline_assets,
            current_assets,
            baseline_meta={
                "id": baseline.id,
                "name": baseline.name,
                "task_id": baseline.task_id,
                "task_name": baseline_task.name if baseline_task else "",
                "code_path": baseline_path,
                "language": baseline.language,
            },
            current_meta={
                "task_id": task.id,
                "task_name": task.name,
                "code_path": task.code_path,
                "language": task.language,
            },
        )

        name = req.name.strip() or f"Diff: {baseline.name} vs {task.name}"
        diff_report = DiffReport(
            name=name,
            baseline_id=baseline.id,
            task_id=task.id,
            diff_json=json.dumps(diff, ensure_ascii=False),
            added_count=diff["summary"]["added"],
            removed_count=diff["summary"]["removed"],
            changed_count=diff["summary"]["changed"],
            risk_level=diff["summary"]["risk_level"],
            created_by=user.id,
        )
        diff_report = await self.diff_repo.create(diff_report)
        await self.db.commit()
        logger.info(
            "Diff report created by user %d: %s (id=%d, +%d/-%d/~%d)",
            user.id, name, diff_report.id,
            diff_report.added_count, diff_report.removed_count, diff_report.changed_count,
        )

        self.db.expire_all()
        saved = await self.diff_repo.find_by_id(diff_report.id)
        return self._build_diff_detail(saved)

    async def list_diffs(
        self, page: int = 1, page_size: int = 20, user: CurrentUser | None = None
    ) -> PageResponse[DiffReportDTO]:
        scope_user = None if (user is None or self._is_admin(user)) else user.id
        items, total = await self.diff_repo.find_all(page, page_size, created_by=scope_user)
        total_pages = (total + page_size - 1) // page_size
        return PageResponse(
            items=[self._build_diff_dto(d) for d in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_diff_detail(self, diff_id: int, user: CurrentUser) -> DiffReportDetailDTO:
        diff_report = await self.diff_repo.find_by_id(diff_id)
        if not diff_report:
            raise NotFoundException(f"差异报告不存在: {diff_id}")
        self._assert_owner(diff_report, user, "差异报告")
        return self._build_diff_detail(diff_report)

    async def delete_diff(self, diff_id: int) -> bool:
        deleted = await self.diff_repo.delete_by_id(diff_id)
        if deleted:
            logger.info("Deleted diff report: id=%d", diff_id)
        return deleted

    # ---------------- DTO builders ----------------

    @staticmethod
    def _build_baseline_dto(b: Baseline) -> BaselineDTO:
        return BaselineDTO(
            id=b.id,
            name=b.name,
            description=b.description or "",
            task_id=b.task_id,
            task_name=b.task.name if b.task else "",
            language=b.language,
            total_assets=b.total_assets,
            risk_level=b.risk_level,
            created_by=b.created_by,
            creator_name=b.creator.username if b.creator else "",
            created_at=b.created_at,
        )

    def _build_baseline_detail(self, b: Baseline) -> BaselineDetailDTO:
        dto = self._build_baseline_dto(b)
        snapshot = json.loads(b.snapshot_json) if b.snapshot_json else {}
        return BaselineDetailDTO(
            **dto.model_dump(),
            assets=snapshot.get("assets", []),
            source_summary=snapshot.get("source_summary"),
        )

    @staticmethod
    def _build_diff_dto(d: DiffReport) -> DiffReportDTO:
        return DiffReportDTO(
            id=d.id,
            name=d.name,
            baseline_id=d.baseline_id,
            baseline_name=d.baseline.name if d.baseline else "",
            task_id=d.task_id,
            task_name=d.task.name if d.task else "",
            added_count=d.added_count,
            removed_count=d.removed_count,
            changed_count=d.changed_count,
            risk_level=d.risk_level,
            created_by=d.created_by,
            creator_name=d.creator.username if d.creator else "",
            created_at=d.created_at,
        )

    def _build_diff_detail(self, d: DiffReport) -> DiffReportDetailDTO:
        dto = self._build_diff_dto(d)
        diff = json.loads(d.diff_json) if d.diff_json else {}
        return DiffReportDetailDTO(**dto.model_dump(), diff=diff)
