"""
Service/API layer tests for baseline & diff report.
Runs against an isolated SQLite database (see conftest.py).
"""

import asyncio
import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base
from app.entities.models import AnalysisResult, AnalysisTask, TaskStatus, User, UserRole
from app.schemas.baseline import BaselineCreateRequest
from app.services.baseline_service import BaselineService

# NullPool: avoid cross-event-loop connection reuse between asyncio.run calls
engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def run(coro):
    return asyncio.run(coro)


def make_report(components, language="c"):
    return {
        "cbom_version": "1.0",
        "metadata": {"tool": "CBOM Analyzer", "language": language},
        "summary": {"total_matches": 0, "risk_level": "low"},
        "components": components,
    }


def make_component(name, library_key, signature, file="main.c"):
    return {
        "name": name,
        "library_key": library_key,
        "type": "tls_library",
        "functions": [{
            "signature": signature,
            "match_type": "exact",
            "best_confidence": 1.0,
            "locations": [{
                "file": file, "line": 1, "matched_text": signature,
                "confidence": 1.0, "context": f"{signature}();",
            }],
        }],
    }


PROJECT_A = "/scans/project-a"
PROJECT_B = "/scans/project-b"


async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_user() -> int:
    async with TestSession() as session:
        user = User(username="tester", password_hash="x", role=UserRole.ADMIN)
        session.add(user)
        await session.commit()
        return user.id


async def _make_task(user_id, name, code_path, language, status, report=None) -> int:
    async with TestSession() as session:
        task = AnalysisTask(
            name=name, language=language, code_path=code_path,
            status=status, created_by=user_id,
        )
        session.add(task)
        await session.flush()
        if report is not None:
            session.add(AnalysisResult(
                task_id=task.id,
                report_json=json.dumps(report, ensure_ascii=False),
                total_files_scanned=1,
                total_matches=len(report.get("components", [])),
                total_components=len(report.get("components", [])),
                risk_level="info",
            ))
        await session.commit()
        return task.id


async def _make_baseline(user_id, name="基线A", code_path=PROJECT_A, language="c") -> int:
    task_id = await _make_task(
        user_id, f"{name}-来源", code_path, language, TaskStatus.COMPLETED,
        report=make_report([make_component("AES", "aes", "aes_encrypt")], language),
    )
    async with TestSession() as session:
        service = BaselineService(session)
        dto = await service.create_baseline(BaselineCreateRequest(name=name, task_id=task_id), user_id)
        return dto.id


class TestBaselineServiceValidation:
    def setup_method(self):
        run(_reset_db())
        self.user_id = run(_seed_user())

    def test_generate_diff_baseline_not_found(self):
        async def _test():
            task_id = await _make_task(
                self.user_id, "task", PROJECT_A, "c", TaskStatus.COMPLETED,
                report=make_report([]),
            )
            async with TestSession() as session:
                service = BaselineService(session)
                await service.generate_diff(999, task_id, self.user_id)

        with pytest.raises(ValueError, match="Baseline not found"):
            run(_test())

    def test_generate_diff_cross_project_rejected(self):
        async def _test():
            baseline_id = await _make_baseline(self.user_id, code_path=PROJECT_A)
            other_task = await _make_task(
                self.user_id, "其他项目", PROJECT_B, "c", TaskStatus.COMPLETED,
                report=make_report([make_component("AES", "aes", "aes_encrypt")]),
            )
            async with TestSession() as session:
                service = BaselineService(session)
                await service.generate_diff(baseline_id, other_task, self.user_id)

        with pytest.raises(ValueError, match="代码路径与基线不一致"):
            run(_test())

    def test_generate_diff_language_mismatch_rejected(self):
        async def _test():
            baseline_id = await _make_baseline(self.user_id, language="c")
            py_task = await _make_task(
                self.user_id, "python版", PROJECT_A, "python", TaskStatus.COMPLETED,
                report=make_report([], "python"),
            )
            async with TestSession() as session:
                service = BaselineService(session)
                await service.generate_diff(baseline_id, py_task, self.user_id)

        with pytest.raises(ValueError, match="代码语言与基线不一致"):
            run(_test())

    def test_generate_diff_unfinished_task_rejected(self):
        """分析尚无结果（未完成）时不允许生成差异。"""
        async def _test():
            baseline_id = await _make_baseline(self.user_id)
            pending_task = await _make_task(
                self.user_id, "未完成", PROJECT_A, "c", TaskStatus.PENDING,
            )
            async with TestSession() as session:
                service = BaselineService(session)
                await service.generate_diff(baseline_id, pending_task, self.user_id)

        with pytest.raises(ValueError, match="只有已完成的分析任务才能生成差异报告"):
            run(_test())

    def test_generate_diff_with_empty_analysis_result(self):
        """已完成但结果为空（无组件）的分析可以生成差异，基线资产全部计为移除。"""
        async def _test():
            baseline_id = await _make_baseline(self.user_id)
            empty_task = await _make_task(
                self.user_id, "空结果", PROJECT_A, "c", TaskStatus.COMPLETED,
                report=make_report([]),
            )
            async with TestSession() as session:
                service = BaselineService(session)
                detail = await service.generate_diff(baseline_id, empty_task, self.user_id)
                return detail

        detail = run(_test())
        assert detail.diff["summary"]["removed"] == 1
        assert detail.diff["summary"]["added"] == 0
        assert detail.report.removed_count == 1

    def test_generate_diff_success_for_matching_project(self):
        """代码路径与语言均一致时正常生成差异。"""
        async def _test():
            baseline_id = await _make_baseline(self.user_id)
            new_task = await _make_task(
                self.user_id, "同项目v2", PROJECT_A, "c", TaskStatus.COMPLETED,
                report=make_report([
                    make_component("AES", "aes", "aes_encrypt"),
                    make_component("RSA", "rsa", "rsa_sign"),
                ]),
            )
            async with TestSession() as session:
                service = BaselineService(session)
                return await service.generate_diff(baseline_id, new_task, self.user_id)

        detail = run(_test())
        assert detail.diff["summary"]["added"] == 1
        assert detail.diff["summary"]["removed"] == 0
        assert detail.diff["summary"]["unchanged"] == 1
        assert detail.report.added_count == 1

    def test_create_baseline_from_unfinished_task_rejected(self):
        async def _test():
            task_id = await _make_task(
                self.user_id, "未完成", PROJECT_A, "c", TaskStatus.RUNNING,
            )
            async with TestSession() as session:
                service = BaselineService(session)
                await service.create_baseline(
                    BaselineCreateRequest(name="bad", task_id=task_id), self.user_id,
                )

        with pytest.raises(ValueError, match="只有已完成的分析任务才能保存为基线"):
            run(_test())


class TestBaselineApiAuth:
    """接口层：未登录访问一律 401。"""

    def test_unauthenticated_access_rejected(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            assert client.get("/api/baselines").status_code == 401
            assert client.post("/api/baselines", json={"name": "x", "task_id": 1}).status_code == 401
            assert client.get("/api/baselines/1").status_code == 401
            assert client.delete("/api/baselines/1").status_code == 401
            assert client.post("/api/baselines/1/diff", json={"task_id": 1}).status_code == 401
            assert client.get("/api/baselines/1/diffs").status_code == 401
            assert client.get("/api/baselines/diffs/1").status_code == 401
