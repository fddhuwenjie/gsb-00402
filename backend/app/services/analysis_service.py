"""
Core analysis service that orchestrates YARA signature matching against source code.
"""

import json
import logging
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzers import get_analyzer
from app.config import settings
from app.core.cbom_generator import CBOMGenerator
from app.core.fuzzy_matcher import FuzzyMatcher
from app.core.yara_parser import YaraParser
from app.entities.models import AnalysisTask, AnalysisResult, TaskStatus
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.signature_repository import SignatureRepository
from app.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisTaskDTO,
    AnalysisDetailDTO,
    AnalysisResultDTO,
)
from app.schemas.common import PageResponse

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.analysis_repo = AnalysisRepository(db)
        self.sig_repo = SignatureRepository(db)
        self.parser = YaraParser()
        self.matcher = FuzzyMatcher(threshold=settings.FUZZY_MATCH_THRESHOLD)
        self.cbom_gen = CBOMGenerator()

    @staticmethod
    def _validate_code_path(raw_path: str, allow_temp: bool = False) -> Path:
        """Normalize and validate the scan path to prevent directory traversal."""
        code_path = Path(raw_path).resolve()
        
        # 允许临时目录（用于文件上传场景）
        if allow_temp and str(code_path).startswith("/tmp/"):
            if not code_path.exists():
                raise ValueError(f"代码路径不存在: {raw_path}")
            if not code_path.is_dir():
                raise ValueError(f"代码路径不是目录: {raw_path}")
            return code_path
        
        allowed_root = Path(settings.CODE_SCAN_DIR).resolve()
        if not str(code_path).startswith(str(allowed_root)):
            raise ValueError(
                f"代码路径必须在 {settings.CODE_SCAN_DIR} 目录下，不允许路径穿越"
            )
        if not code_path.exists():
            raise ValueError(f"代码路径不存在: {raw_path}")
        if not code_path.is_dir():
            raise ValueError(f"代码路径不是目录: {raw_path}")
        return code_path

    async def create_and_run(self, req: AnalysisCreateRequest, user_id: int, allow_temp: bool = False) -> AnalysisDetailDTO:
        sig_files = await self.sig_repo.find_by_ids(req.signature_file_ids)
        if not sig_files:
            raise ValueError("未找到有效的特征文件")

        code_path = self._validate_code_path(req.code_path, allow_temp=allow_temp)

        # Project identity for baseline comparison. Uploaded projects supply a
        # stable key (their temp dir changes each upload); on-disk scans fall
        # back to the resolved code path.
        project_key = (req.project_key or "").strip() or str(code_path)

        task = AnalysisTask(
            name=req.name,
            language=req.language.lower(),
            code_path=str(code_path),
            project_key=project_key,
            status=TaskStatus.PENDING,
            created_by=user_id,
        )
        task.signature_files = list(sig_files)
        task = await self.analysis_repo.create(task)
        await self.db.commit()

        try:
            await self.analysis_repo.update_status(task.id, TaskStatus.RUNNING)
            await self.db.commit()

            result = await self._run_analysis(task, sig_files)

            await self.analysis_repo.update_status(task.id, TaskStatus.COMPLETED)
            await self.db.commit()

            logger.info(
                "Analysis completed: task=%d, matches=%d, components=%d",
                task.id, result.total_matches, result.total_components,
            )
        except Exception as e:
            logger.error("Analysis failed for task %d: %s", task.id, e)
            await self.analysis_repo.update_status(task.id, TaskStatus.FAILED, str(e))
            await self.db.commit()
            raise

        task_id = task.id
        self.db.expire_all()
        task = await self.analysis_repo.find_by_id(task_id)
        return self._build_detail_dto(task)

    async def _run_analysis(self, task: AnalysisTask, sig_files) -> AnalysisResult:
        start_time = time.time()

        all_patterns = []
        sig_file_names = []
        for sf in sig_files:
            rules = self.parser.parse_file(sf.file_path)
            sig_file_names.append(sf.original_filename)
            for rule in rules:
                for sig in rule.signatures:
                    if sig.pattern and not sig.pattern.startswith("hex:"):
                        all_patterns.append(sig.pattern)

        if not all_patterns:
            raise ValueError("No valid function patterns found in signature files")

        analyzer = get_analyzer(task.language)
        file_tokens = analyzer.scan_directory(task.code_path)

        all_matches = []
        for file_path, tokens in file_tokens:
            rel_path = file_path
            try:
                rel_path = str(Path(file_path).relative_to(task.code_path))
            except ValueError:
                pass

            matches = self.matcher.match_tokens_in_file(tokens, all_patterns, rel_path)
            all_matches.extend(matches)

        scan_duration = time.time() - start_time
        total_files = len(file_tokens)

        report = self.cbom_gen.generate(
            matches=all_matches,
            target_path=task.code_path,
            language=task.language,
            signature_files=sig_file_names,
            total_files_scanned=total_files,
            scan_duration=scan_duration,
        )

        result = AnalysisResult(
            task_id=task.id,
            report_json=json.dumps(report, ensure_ascii=False),
            total_files_scanned=total_files,
            total_matches=len(all_matches),
            total_components=len(report.get("components", [])),
            risk_level=report["summary"]["risk_level"],
            scan_duration=scan_duration,
        )
        return await self.analysis_repo.save_result(result)

    async def list_analyses(self, page: int = 1, page_size: int = 20) -> PageResponse[AnalysisTaskDTO]:
        items, total = await self.analysis_repo.find_all(page, page_size)
        total_pages = (total + page_size - 1) // page_size

        dtos = []
        for t in items:
            dto = AnalysisTaskDTO(
                id=t.id,
                name=t.name,
                language=t.language,
                code_path=t.code_path,
                project_key=t.project_key,
                status=t.status.value,
                error_message=t.error_message,
                created_by=t.created_by,
                creator_name=t.creator.username if t.creator else "",
                signature_file_names=[sf.name for sf in t.signature_files],
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            dtos.append(dto)

        return PageResponse(
            items=dtos,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_analysis_detail(self, task_id: int) -> AnalysisDetailDTO:
        task = await self.analysis_repo.find_by_id(task_id)
        if not task:
            raise ValueError(f"Analysis task not found: {task_id}")
        return self._build_detail_dto(task)

    async def get_report_json(self, task_id: int) -> dict:
        task = await self.analysis_repo.find_by_id(task_id)
        if not task:
            raise ValueError(f"Analysis task not found: {task_id}")
        if not task.result:
            raise ValueError("Analysis has no result yet")
        return json.loads(task.result.report_json)

    async def delete_analysis(self, task_id: int) -> bool:
        return await self.analysis_repo.delete_by_id(task_id)

    def _build_detail_dto(self, task: AnalysisTask) -> AnalysisDetailDTO:
        task_dto = AnalysisTaskDTO(
            id=task.id,
            name=task.name,
            language=task.language,
            code_path=task.code_path,
            project_key=task.project_key,
            status=task.status.value,
            error_message=task.error_message,
            created_by=task.created_by,
            creator_name=task.creator.username if task.creator else "",
            signature_file_names=[sf.name for sf in task.signature_files],
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

        result_dto = None
        if task.result:
            result_dto = AnalysisResultDTO(
                id=task.result.id,
                task_id=task.result.task_id,
                total_files_scanned=task.result.total_files_scanned,
                total_matches=task.result.total_matches,
                total_components=task.result.total_components,
                risk_level=task.result.risk_level,
                scan_duration=task.result.scan_duration,
                report=json.loads(task.result.report_json),
                created_at=task.result.created_at,
            )

        return AnalysisDetailDTO(task=task_dto, result=result_dto)
