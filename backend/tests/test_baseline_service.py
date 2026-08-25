"""
Service-level tests for baseline/diff access control and project validation.

These exercise BaselineService directly with mocked repositories — no database
or HTTP layer required.
"""

import datetime
from types import SimpleNamespace

import pytest

from app.controllers.deps import CurrentUser
from app.exceptions.handlers import ForbiddenException, NotFoundException
from app.schemas.baseline import BaselineCreateRequest, DiffCreateRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _completed_report():
    return {
        "metadata": {"language": "c"},
        "components": [
            {
                "library_key": "mbedtls",
                "name": "Mbed TLS",
                "type": "crypto_library",
                "functions": [
                    {
                        "signature": "mbedtls_ssl_read",
                        "match_type": "exact",
                        "best_confidence": 1.0,
                        "locations": [
                            {"file": "ssl.c", "line": 10, "matched_text": "mbedtls_ssl_read",
                             "confidence": 1.0, "context": "x"}
                        ],
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# create_baseline — ownership
# ---------------------------------------------------------------------------

class TestCreateBaselineOwnership:
    @pytest.mark.anyio
    async def test_rejects_creating_baseline_from_another_users_task(self, service, user1, user2):
        from tests.conftest import make_task
        task = make_task(task_id=10, owner_id=user2.id, report=_completed_report())
        service.analysis_repo.find_by_id.return_value = task

        req = BaselineCreateRequest(name="b", task_id=10)
        with pytest.raises(ForbiddenException) as exc:
            await service.create_baseline(req, user1)
        assert "来源分析任务" in str(exc.value)
        service.repo.create.assert_not_called()

    @pytest.mark.anyio
    async def test_allows_owner_to_create_baseline(self, service, user1, mock_db):
        from tests.conftest import make_baseline, make_task
        task = make_task(task_id=10, owner_id=user1.id, report=_completed_report())
        service.analysis_repo.find_by_id.return_value = task
        baseline = make_baseline(baseline_id=5, owner_id=user1.id, report=_completed_report())
        service.repo.create.return_value = baseline

        req = BaselineCreateRequest(name="my-baseline", task_id=10)
        result = await service.create_baseline(req, user1)
        assert result.id == 5
        service.repo.create.assert_called_once()
        assert service.repo.create.call_args[0][0].created_by == user1.id

    @pytest.mark.anyio
    async def test_admin_cannot_create_baseline_from_another_users_task(self, service, admin, user2, mock_db):
        """管理员也不能绕过归属限制，不能基于他人任务创建基线。"""
        from tests.conftest import make_task
        task = make_task(task_id=10, owner_id=user2.id, report=_completed_report())
        service.analysis_repo.find_by_id.return_value = task

        req = BaselineCreateRequest(name="admin-b", task_id=10)
        with pytest.raises(ForbiddenException):
            await service.create_baseline(req, admin)
        service.repo.create.assert_not_called()

    @pytest.mark.anyio
    async def test_rejects_non_completed_task(self, service, user1):
        from tests.conftest import make_task
        task = make_task(task_id=10, owner_id=user1.id, status="pending")
        service.analysis_repo.find_by_id.return_value = task

        req = BaselineCreateRequest(name="b", task_id=10)
        with pytest.raises(ValueError):
            await service.create_baseline(req, user1)

    @pytest.mark.anyio
    async def test_raises_when_task_missing(self, service, user1):
        service.analysis_repo.find_by_id.return_value = None
        req = BaselineCreateRequest(name="b", task_id=999)
        with pytest.raises(NotFoundException):
            await service.create_baseline(req, user1)


# ---------------------------------------------------------------------------
# get/delete baseline — ownership
# ---------------------------------------------------------------------------

class TestBaselineAccess:
    @pytest.mark.anyio
    async def test_get_baseline_cross_user_forbidden(self, service, user1, user2):
        from tests.conftest import make_baseline
        service.repo.find_by_id.return_value = make_baseline(baseline_id=3, owner_id=user2.id)
        with pytest.raises(ForbiddenException):
            await service.get_baseline(3, user1)

    @pytest.mark.anyio
    async def test_get_baseline_owner_allowed(self, service, user1):
        from tests.conftest import make_baseline
        service.repo.find_by_id.return_value = make_baseline(baseline_id=3, owner_id=user1.id, report=_completed_report())
        result = await service.get_baseline(3, user1)
        assert result.id == 3

    @pytest.mark.anyio
    async def test_admin_cannot_access_another_users_baseline(self, service, admin, user2):
        """管理员也不能查看他人的基线。"""
        from tests.conftest import make_baseline
        service.repo.find_by_id.return_value = make_baseline(baseline_id=3, owner_id=user2.id)
        with pytest.raises(ForbiddenException):
            await service.get_baseline(3, admin)

    @pytest.mark.anyio
    async def test_get_baseline_not_found(self, service, user1):
        service.repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await service.get_baseline(999, user1)

    @pytest.mark.anyio
    async def test_delete_cross_user_forbidden(self, service, user1, user2):
        from tests.conftest import make_baseline
        service.repo.find_by_id.return_value = make_baseline(baseline_id=4, owner_id=user2.id)
        with pytest.raises(ForbiddenException):
            await service.delete_baseline(4, user1)
        service.repo.delete_by_id.assert_not_called()

    @pytest.mark.anyio
    async def test_delete_owner_allowed(self, service, user1):
        from tests.conftest import make_baseline
        service.repo.find_by_id.return_value = make_baseline(baseline_id=4, owner_id=user1.id)
        service.repo.delete_by_id.return_value = True
        assert await service.delete_baseline(4, user1) is True
        service.repo.delete_by_id.assert_called_once_with(4)

    @pytest.mark.anyio
    async def test_delete_missing_returns_false(self, service, user1):
        service.repo.find_by_id.return_value = None
        assert await service.delete_baseline(404, user1) is False


# ---------------------------------------------------------------------------
# list_baselines — owner filtering
# ---------------------------------------------------------------------------

class TestListBaselinesFiltering:
    @pytest.mark.anyio
    async def test_regular_user_sees_only_own_baselines(self, service, user1):
        from tests.conftest import make_baseline
        own = make_baseline(baseline_id=1, owner_id=user1.id)
        service.repo.find_all.return_value = ([own], 1)
        result = await service.list_baselines(user1)
        assert result.total == 1
        service.repo.find_all.assert_called_once_with(1, 20, owner_id=user1.id)

    @pytest.mark.anyio
    async def test_admin_also_sees_only_own_baselines(self, service, admin):
        """管理员也只能看到自己的基线列表。"""
        service.repo.find_all.return_value = ([], 0)
        await service.list_baselines(admin)
        service.repo.find_all.assert_called_once_with(1, 20, owner_id=admin.id)


# ---------------------------------------------------------------------------
# create_diff — same project + ownership
# ---------------------------------------------------------------------------

class TestCreateDiffValidation:
    @pytest.mark.anyio
    async def test_cross_project_path_rejected(self, service, user1):
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(baseline_id=1, owner_id=user1.id, code_path="/code/project-a", report=_completed_report())
        task = make_task(task_id=2, owner_id=user1.id, code_path="/code/project-b", report=_completed_report())
        service.repo.find_by_id.return_value = baseline
        service.analysis_repo.find_by_id.return_value = task

        with pytest.raises(ForbiddenException) as exc:
            await service.create_diff(1, 2, user1)
        assert "同一项目" in str(exc.value)
        service.repo.save_diff.assert_not_called()

    @pytest.mark.anyio
    async def test_cross_language_rejected(self, service, user1):
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(baseline_id=1, owner_id=user1.id, language="c", code_path="/code/p", report=_completed_report())
        task = make_task(task_id=2, owner_id=user1.id, language="python", code_path="/code/p", report=_completed_report())
        service.repo.find_by_id.return_value = baseline
        service.analysis_repo.find_by_id.return_value = task

        with pytest.raises(ForbiddenException) as exc:
            await service.create_diff(1, 2, user1)
        assert "语言不一致" in str(exc.value)

    @pytest.mark.anyio
    async def test_cross_user_baseline_rejected(self, service, user1, user2):
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(baseline_id=1, owner_id=user2.id, code_path="/code/p", report=_completed_report())
        task = make_task(task_id=2, owner_id=user1.id, code_path="/code/p", report=_completed_report())
        service.repo.find_by_id.return_value = baseline
        service.analysis_repo.find_by_id.return_value = task

        with pytest.raises(ForbiddenException):
            await service.create_diff(1, 2, user1)

    @pytest.mark.anyio
    async def test_cross_user_task_rejected(self, service, user1, user2):
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(baseline_id=1, owner_id=user1.id, code_path="/code/p", report=_completed_report())
        task = make_task(task_id=2, owner_id=user2.id, code_path="/code/p", report=_completed_report())
        service.repo.find_by_id.return_value = baseline
        service.analysis_repo.find_by_id.return_value = task

        with pytest.raises(ForbiddenException):
            await service.create_diff(1, 2, user1)

    @pytest.mark.anyio
    async def test_same_project_owner_succeeds(self, service, user1, mock_db):
        from tests.conftest import make_baseline, make_diff, make_task
        baseline = make_baseline(baseline_id=1, owner_id=user1.id, code_path="/code/p", report=_completed_report())
        task = make_task(task_id=2, owner_id=user1.id, code_path="/code/p", report=_completed_report())
        service.repo.find_by_id.return_value = baseline
        service.analysis_repo.find_by_id.return_value = task
        service.repo.find_diff_by_baseline_and_task.return_value = None
        diff = make_diff(diff_id=7, owner_id=user1.id, baseline_id=1, task_id=2)
        service.repo.save_diff.return_value = diff

        result = await service.create_diff(1, 2, user1)
        assert result.id == 7
        service.repo.save_diff.assert_called_once()

    @pytest.mark.anyio
    async def test_admin_cannot_diff_across_owners(self, service, admin, user2, mock_db):
        """管理员也不能用他人的基线和任务生成差异。"""
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(baseline_id=1, owner_id=user2.id, code_path="/code/p", report=_completed_report())
        task = make_task(task_id=2, owner_id=user2.id, code_path="/code/p", report=_completed_report())
        service.repo.find_by_id.return_value = baseline
        service.analysis_repo.find_by_id.return_value = task

        with pytest.raises(ForbiddenException):
            await service.create_diff(1, 2, admin)
        service.repo.save_diff.assert_not_called()

    @pytest.mark.anyio
    async def test_different_temp_paths_same_project_key_allowed(self, service, user1, mock_db):
        """上传场景：临时路径不同但 project_key 相同 → 允许对比。"""
        from tests.conftest import make_baseline, make_diff, make_task
        baseline = make_baseline(
            baseline_id=1, owner_id=user1.id, language="c",
            code_path="/tmp/cbom_scan_abc", project_key="myapp-v1",
            report=_completed_report(),
        )
        task = make_task(
            task_id=2, owner_id=user1.id, language="c",
            code_path="/tmp/cbom_scan_xyz", project_key="myapp-v1",
            report=_completed_report(),
        )
        service.repo.find_by_id.return_value = baseline
        service.analysis_repo.find_by_id.return_value = task
        service.repo.find_diff_by_baseline_and_task.return_value = None
        service.repo.save_diff.return_value = make_diff(diff_id=9, owner_id=user1.id)

        result = await service.create_diff(1, 2, user1)
        assert result.id == 9

    @pytest.mark.anyio
    async def test_temp_path_different_project_key_rejected(self, service, user1):
        """临时路径跨项目（project_key 不同）即使语言相同也必须拒绝。"""
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(
            baseline_id=1, owner_id=user1.id, language="c",
            code_path="/tmp/cbom_scan_abc", project_key="project-alpha",
            report=_completed_report(),
        )
        task = make_task(
            task_id=2, owner_id=user1.id, language="c",
            code_path="/tmp/cbom_scan_xyz", project_key="project-beta",
            report=_completed_report(),
        )
        service.repo.find_by_id.return_value = baseline
        service.analysis_repo.find_by_id.return_value = task

        with pytest.raises(ForbiddenException) as exc:
            await service.create_diff(1, 2, user1)
        assert "同一项目" in str(exc.value)
        service.repo.save_diff.assert_not_called()

    @pytest.mark.anyio
    async def test_missing_project_key_rejected(self, service, user1):
        """基线或任务缺少 project_key 时拒绝对比。"""
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(
            baseline_id=1, owner_id=user1.id, code_path="/code/p",
            project_key="", report=_completed_report(),
        )
        task = make_task(
            task_id=2, owner_id=user1.id, code_path="/code/p",
            project_key="", report=_completed_report(),
        )
        service.repo.find_by_id.return_value = baseline
        service.analysis_repo.find_by_id.return_value = task

        with pytest.raises(ForbiddenException):
            await service.create_diff(1, 2, user1)


# ---------------------------------------------------------------------------
# get_diff / list_diffs — ownership
# ---------------------------------------------------------------------------

class TestDiffAccess:
    @pytest.mark.anyio
    async def test_get_diff_cross_user_forbidden(self, service, user1, user2):
        from tests.conftest import make_diff
        service.repo.find_diff_by_id.return_value = make_diff(diff_id=5, owner_id=user2.id)
        with pytest.raises(ForbiddenException):
            await service.get_diff(5, user1)

    @pytest.mark.anyio
    async def test_get_diff_owner_allowed(self, service, user1):
        from tests.conftest import make_diff
        service.repo.find_diff_by_id.return_value = make_diff(diff_id=5, owner_id=user1.id)
        result = await service.get_diff(5, user1)
        assert result.id == 5

    @pytest.mark.anyio
    async def test_get_diff_not_found(self, service, user1):
        service.repo.find_diff_by_id.return_value = None
        with pytest.raises(NotFoundException):
            await service.get_diff(404, user1)

    @pytest.mark.anyio
    async def test_list_diffs_cross_user_task_forbidden(self, service, user1, user2):
        from tests.conftest import make_task
        task = make_task(task_id=3, owner_id=user2.id)
        service.analysis_repo.find_by_id.return_value = task
        with pytest.raises(ForbiddenException):
            await service.list_diffs_by_task(3, user1)

    @pytest.mark.anyio
    async def test_list_diffs_owner_filters_by_owner(self, service, user1):
        from tests.conftest import make_diff, make_task
        task = make_task(task_id=3, owner_id=user1.id)
        service.analysis_repo.find_by_id.return_value = task
        service.repo.find_diffs_by_task.return_value = [make_diff(diff_id=1, owner_id=user1.id)]
        result = await service.list_diffs_by_task(3, user1)
        assert len(result) == 1
        service.repo.find_diffs_by_task.assert_called_once_with(3, owner_id=user1.id)

    @pytest.mark.anyio
    async def test_admin_list_diffs_also_filtered_by_owner(self, service, admin, user2):
        """管理员查看差异列表也只能看到自己的。"""
        from tests.conftest import make_task
        task = make_task(task_id=3, owner_id=admin.id)
        service.analysis_repo.find_by_id.return_value = task
        service.repo.find_diffs_by_task.return_value = []
        await service.list_diffs_by_task(3, admin)
        service.repo.find_diffs_by_task.assert_called_once_with(3, owner_id=admin.id)

    @pytest.mark.anyio
    async def test_admin_cannot_list_diffs_of_another_users_task(self, service, admin, user2):
        """管理员不能查看他人任务的差异列表。"""
        from tests.conftest import make_task
        task = make_task(task_id=3, owner_id=user2.id)
        service.analysis_repo.find_by_id.return_value = task
        with pytest.raises(ForbiddenException):
            await service.list_diffs_by_task(3, admin)


# ---------------------------------------------------------------------------
# maybe_create_diff_for_task — auto-diff failure must raise clearly
# ---------------------------------------------------------------------------

class TestAutoDiffFailure:
    @pytest.mark.anyio
    async def test_missing_baseline_raises_not_found(self, service, user1):
        from tests.conftest import make_task
        task = make_task(task_id=1, owner_id=user1.id, report=_completed_report())
        service.repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException) as exc:
            await service.maybe_create_diff_for_task(task, 999, user1)
        assert "999" in str(exc.value)

    @pytest.mark.anyio
    async def test_cross_project_raises_forbidden(self, service, user1):
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(baseline_id=1, owner_id=user1.id, code_path="/code/a", report=_completed_report())
        task = make_task(task_id=2, owner_id=user1.id, code_path="/code/b", report=_completed_report())
        service.repo.find_by_id.return_value = baseline
        with pytest.raises(ForbiddenException) as exc:
            await service.maybe_create_diff_for_task(task, 1, user1)
        assert "同一项目" in str(exc.value)
        service.repo.save_diff.assert_not_called()

    @pytest.mark.anyio
    async def test_cross_user_baseline_raises_forbidden(self, service, user1, user2):
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(baseline_id=1, owner_id=user2.id, code_path="/code/p", report=_completed_report())
        task = make_task(task_id=2, owner_id=user1.id, code_path="/code/p", report=_completed_report())
        service.repo.find_by_id.return_value = baseline
        with pytest.raises(ForbiddenException):
            await service.maybe_create_diff_for_task(task, 1, user1)

    @pytest.mark.anyio
    async def test_cross_user_task_raises_forbidden(self, service, user1, user2):
        """自动生成差异时，当前分析任务属于他人也必须拒绝（即使基线是自己的）。"""
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(
            baseline_id=1, owner_id=user1.id, code_path="/code/p",
            project_key="proj", report=_completed_report(),
        )
        task = make_task(
            task_id=2, owner_id=user2.id, code_path="/code/p",
            project_key="proj", report=_completed_report(),
        )
        service.repo.find_by_id.return_value = baseline
        with pytest.raises(ForbiddenException) as exc:
            await service.maybe_create_diff_for_task(task, 1, user1)
        assert "当前分析任务" in str(exc.value)
        service.repo.save_diff.assert_not_called()

    @pytest.mark.anyio
    async def test_admin_cannot_autodiff_another_users_task(self, service, admin, user2):
        """管理员也不能为他人的任务自动生成差异。"""
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(
            baseline_id=1, owner_id=user2.id, code_path="/code/p",
            project_key="proj", report=_completed_report(),
        )
        task = make_task(
            task_id=2, owner_id=user2.id, code_path="/code/p",
            project_key="proj", report=_completed_report(),
        )
        service.repo.find_by_id.return_value = baseline
        with pytest.raises(ForbiddenException):
            await service.maybe_create_diff_for_task(task, 1, admin)

    @pytest.mark.anyio
    async def test_temp_path_cross_project_raises_forbidden(self, service, user1):
        """上传临时路径下 project_key 不同即跨项目，必须拒绝。"""
        from tests.conftest import make_baseline, make_task
        baseline = make_baseline(
            baseline_id=1, owner_id=user1.id, language="c",
            code_path="/tmp/cbom_scan_aaa", project_key="alpha",
            report=_completed_report(),
        )
        task = make_task(
            task_id=2, owner_id=user1.id, language="c",
            code_path="/tmp/cbom_scan_bbb", project_key="beta",
            report=_completed_report(),
        )
        service.repo.find_by_id.return_value = baseline
        with pytest.raises(ForbiddenException) as exc:
            await service.maybe_create_diff_for_task(task, 1, user1)
        assert "同一项目" in str(exc.value)
        service.repo.save_diff.assert_not_called()

    @pytest.mark.anyio
    async def test_no_result_raises_value_error(self, service, user1):
        from tests.conftest import make_task
        from app.entities.models import TaskStatus
        task = SimpleNamespace(
            id=2, name="t", language="c", code_path="/code/p", project_key="/code/p",
            status=TaskStatus.COMPLETED, created_by=user1.id, result=None,
            created_at=datetime.datetime.utcnow(),
        )
        with pytest.raises(ValueError):
            await service.maybe_create_diff_for_task(task, 1, user1)

    @pytest.mark.anyio
    async def test_no_baseline_id_returns_none(self, service, user1):
        from tests.conftest import make_task
        task = make_task(task_id=2, owner_id=user1.id, report=_completed_report())
        assert await service.maybe_create_diff_for_task(task, None, user1) is None

    @pytest.mark.anyio
    async def test_success_persists_diff(self, service, user1, mock_db):
        from tests.conftest import make_baseline, make_diff, make_task
        baseline = make_baseline(baseline_id=1, owner_id=user1.id, code_path="/code/p", report=_completed_report())
        task = make_task(task_id=2, owner_id=user1.id, code_path="/code/p", report=_completed_report())
        service.repo.find_by_id.return_value = baseline
        service.repo.save_diff.return_value = make_diff(diff_id=11, owner_id=user1.id)

        result = await service.maybe_create_diff_for_task(task, 1, user1)
        assert result.id == 11
        service.repo.save_diff.assert_called_once()
        saved = service.repo.save_diff.call_args[0][0]
        assert saved.created_by == user1.id
