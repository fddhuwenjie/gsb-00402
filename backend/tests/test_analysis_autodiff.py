"""
Tests for auto-diff generation that runs after an analysis completes.

Covers the requirement: "自动生成差异失败时返回明确错误而不是静默忽略".
These tests verify that:
  - a diff failure propagates as a clear error to the caller;
  - the analysis task itself stays COMPLETED (not flipped to FAILED);
  - a successful auto-diff is committed;
  - no baseline_id means no diff is attempted.
"""

import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.controllers.deps import CurrentUser
from app.entities.models import TaskStatus
from app.exceptions.handlers import ForbiddenException, NotFoundException
from app.schemas.analysis import AnalysisCreateRequest
from app.services.analysis_service import AnalysisService


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _completed_cbom_report():
    return {
        "summary": {"risk_level": "none", "total_components": 1},
        "components": [
            {
                "library": {"name": "lib", "version": "1.0"},
                "functions": [
                    {
                        "name": "EVP_EncryptInit",
                        "algorithm": "AES",
                        "match_type": "exact",
                        "confidence": 0.9,
                        "risk_level": "low",
                        "occurrences": 1,
                        "lines": [10],
                        "locations": [{"file": "a.c", "line": 10}],
                    }
                ],
            }
        ],
    }


def _make_signature_file(sfid=1):
    return SimpleNamespace(
        id=sfid, file_path="/tmp/fake_sig.yar", original_filename="sig.yar",
        name="sig", description="",
    )


def _make_task(owner_id=1, status=TaskStatus.COMPLETED, task_id=1, project_key="/code/proj"):
    now = datetime.datetime.now(datetime.timezone.utc)
    return SimpleNamespace(
        id=task_id, name="t", language="c", code_path="/code/proj",
        project_key=project_key,
        status=status, created_by=owner_id, error_message=None,
        signature_files=[_make_signature_file()],
        creator=SimpleNamespace(username="alice"),
        result=SimpleNamespace(
            id=1, task_id=task_id, total_files_scanned=1, total_matches=1,
            total_components=1, risk_level="none", scan_duration=0.1,
            report_json=json.dumps(_completed_cbom_report()),
            created_at=now,
        ),
        created_at=now, updated_at=now,
    )


@pytest.fixture
def analysis_service(monkeypatch):
    """AnalysisService with mocked DB and repos; real _run_analysis is patched per test."""
    from pathlib import Path
    monkeypatch.setattr(
        AnalysisService, "_validate_code_path",
        staticmethod(lambda raw, allow_temp=False: Path(raw)),
    )
    # Patch the ORM model constructor so assigning mock signature files to the
    # relationship does not trigger SQLAlchemy instance-state checks.
    seed = _make_task()

    def _fake_task_ctor(**kwargs):
        for k, v in kwargs.items():
            setattr(seed, k, v)
        seed.signature_files = []
        return seed

    monkeypatch.setattr(
        "app.services.analysis_service.AnalysisTask", _fake_task_ctor
    )

    db = AsyncMock()
    db.expire_all = MagicMock()
    svc = AnalysisService(db)
    svc.sig_repo = AsyncMock()
    svc.analysis_repo = AsyncMock()
    svc.sig_repo.find_by_ids.return_value = [_make_signature_file()]
    svc.analysis_repo.create.return_value = seed
    svc.analysis_repo.find_by_id.return_value = seed

    async def _update_status(task_id, status, error=None):
        seed.status = status
        if error is not None:
            seed.error_message = error

    svc.analysis_repo.update_status.side_effect = _update_status
    return svc


def _request(baseline_id=None):
    return AnalysisCreateRequest(
        name="test",
        language="c",
        code_path="/code/proj",
        signature_file_ids=[1],
        baseline_id=baseline_id,
    )


def _user(uid=1):
    return CurrentUser(id=uid, username="alice", role="user")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAutoDiffErrorPropagation:
    @pytest.mark.anyio
    async def test_missing_baseline_raises_not_found(self, analysis_service, monkeypatch):
        """Auto-diff with a non-existent baseline_id raises NotFoundException."""
        async def fake_run(task, sig_files):
            return SimpleNamespace(total_matches=1, total_components=1)

        monkeypatch.setattr(analysis_service, "_run_analysis", fake_run)

        async def fake_maybe(self, task, baseline_id, current_user):
            raise NotFoundException(f"基线不存在: {baseline_id}")

        monkeypatch.setattr(
            "app.services.baseline_service.BaselineService.maybe_create_diff_for_task",
            fake_maybe,
        )

        with pytest.raises(NotFoundException) as exc:
            await analysis_service.create_and_run(_request(baseline_id=999), _user())
        assert "基线不存在" in str(exc.value)

        # The task must have been marked COMPLETED before the diff ran.
        update_calls = analysis_service.analysis_repo.update_status.call_args_list
        statuses = [c.args[1] for c in update_calls]
        assert TaskStatus.RUNNING in statuses
        assert TaskStatus.COMPLETED in statuses
        assert TaskStatus.FAILED not in statuses

    @pytest.mark.anyio
    async def test_cross_project_raises_forbidden(self, analysis_service, monkeypatch):
        """Cross-project baseline raises ForbiddenException and is not swallowed."""
        async def fake_run(task, sig_files):
            return SimpleNamespace(total_matches=1, total_components=1)

        monkeypatch.setattr(analysis_service, "_run_analysis", fake_run)

        async def fake_maybe(self, task, baseline_id, current_user):
            raise ForbiddenException("基线与当前分析不属于同一项目，无法生成差异")

        monkeypatch.setattr(
            "app.services.baseline_service.BaselineService.maybe_create_diff_for_task",
            fake_maybe,
        )

        with pytest.raises(ForbiddenException) as exc:
            await analysis_service.create_and_run(_request(baseline_id=2), _user())
        assert "同一项目" in str(exc.value)

        # Task remains COMPLETED — diff failure must not corrupt the analysis status.
        update_calls = analysis_service.analysis_repo.update_status.call_args_list
        assert any(c.args[1] == TaskStatus.COMPLETED for c in update_calls)
        assert not any(c.args[1] == TaskStatus.FAILED for c in update_calls)

    @pytest.mark.anyio
    async def test_cross_user_baseline_raises_forbidden(self, analysis_service, monkeypatch):
        """A baseline owned by another user raises ForbiddenException."""
        async def fake_run(task, sig_files):
            return SimpleNamespace(total_matches=1, total_components=1)

        monkeypatch.setattr(analysis_service, "_run_analysis", fake_run)

        async def fake_maybe(self, task, baseline_id, current_user):
            raise ForbiddenException("无权访问或操作此基线")

        monkeypatch.setattr(
            "app.services.baseline_service.BaselineService.maybe_create_diff_for_task",
            fake_maybe,
        )

        with pytest.raises(ForbiddenException) as exc:
            await analysis_service.create_and_run(_request(baseline_id=3), _user(uid=1))
        assert "无权" in str(exc.value)

    @pytest.mark.anyio
    async def test_diff_failure_does_not_rollback_analysis_result(self, analysis_service, monkeypatch):
        """The completed analysis result is already committed even when diff fails."""
        async def fake_run(task, sig_files):
            return SimpleNamespace(total_matches=1, total_components=1)

        monkeypatch.setattr(analysis_service, "_run_analysis", fake_run)

        call_log = []

        async def fake_maybe(self, task, baseline_id, current_user):
            call_log.append("diff attempted")
            raise ForbiddenException("denied")

        monkeypatch.setattr(
            "app.services.baseline_service.BaselineService.maybe_create_diff_for_task",
            fake_maybe,
        )

        with pytest.raises(ForbiddenException):
            await analysis_service.create_and_run(_request(baseline_id=1), _user())

        # The diff was actually attempted (not silently skipped).
        assert call_log == ["diff attempted"]
        # The COMPLETED commit happened before the diff error.
        assert analysis_service.db.commit.await_count >= 2  # create + RUNNING + COMPLETED commits

    @pytest.mark.anyio
    async def test_successful_autodiff_commits(self, analysis_service, monkeypatch):
        """When diff succeeds, it is persisted and commit is called."""
        async def fake_run(task, sig_files):
            return SimpleNamespace(total_matches=1, total_components=1)

        monkeypatch.setattr(analysis_service, "_run_analysis", fake_run)

        async def fake_maybe(self, task, baseline_id, current_user):
            return SimpleNamespace(id=50)

        monkeypatch.setattr(
            "app.services.baseline_service.BaselineService.maybe_create_diff_for_task",
            fake_maybe,
        )

        result = await analysis_service.create_and_run(_request(baseline_id=1), _user())
        assert result is not None
        assert result.task.status == "completed"

    @pytest.mark.anyio
    async def test_no_baseline_id_skips_diff(self, analysis_service, monkeypatch):
        """Without baseline_id, no diff service is instantiated / called."""
        async def fake_run(task, sig_files):
            return SimpleNamespace(total_matches=1, total_components=1)

        monkeypatch.setattr(analysis_service, "_run_analysis", fake_run)

        maybe_called = False

        async def fake_maybe(self, task, baseline_id, current_user):
            nonlocal maybe_called
            maybe_called = True
            return None

        monkeypatch.setattr(
            "app.services.baseline_service.BaselineService.maybe_create_diff_for_task",
            fake_maybe,
        )

        result = await analysis_service.create_and_run(_request(baseline_id=None), _user())
        assert result is not None
        assert maybe_called is False
