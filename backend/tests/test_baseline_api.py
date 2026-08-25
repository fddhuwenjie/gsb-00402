"""
API-level tests for baseline/diff endpoints.

Verifies authentication boundaries (401), permission mapping (403/404) and
successful responses (200). Business-rule validation (cross-user, cross-project)
is covered in test_baseline_service.py; here we confirm the HTTP layer correctly
propagates those errors to the client.
"""

import pytest

from app.controllers.deps import CurrentUser
from app.exceptions.handlers import ForbiddenException, NotFoundException
from app.schemas.baseline import BaselineDTO, DiffReportDTO
from app.schemas.common import PageResponse
from app.services.baseline_service import BaselineService
from tests.conftest import auth_header, make_baseline, make_diff


# ---------------------------------------------------------------------------
# Unauthenticated access — every endpoint must return 401
# ---------------------------------------------------------------------------

class TestUnauthenticated:
    def test_list_baselines_401(self, client):
        assert client.get("/api/baselines").status_code == 401

    def test_create_baseline_401(self, client):
        assert client.post("/api/baselines", json={"name": "x", "task_id": 1}).status_code == 401

    def test_get_baseline_401(self, client):
        assert client.get("/api/baselines/1").status_code == 401

    def test_delete_baseline_401(self, client):
        assert client.delete("/api/baselines/1").status_code == 401

    def test_create_diff_401(self, client):
        assert client.post("/api/diffs", json={"baseline_id": 1, "task_id": 2}).status_code == 401

    def test_get_diff_401(self, client):
        assert client.get("/api/diffs/1").status_code == 401

    def test_list_diffs_401(self, client):
        assert client.get("/api/diffs", params={"task_id": 1}).status_code == 401

    def test_invalid_token_401(self, client):
        resp = client.get("/api/baselines", headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401

    def test_malformed_authorization_header_401(self, client):
        resp = client.get("/api/baselines", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Authenticated: happy paths
# ---------------------------------------------------------------------------

class TestAuthenticatedSuccess:
    def test_list_baselines_200(self, client, monkeypatch, user1):
        async def fake_list(self, current_user, page=1, page_size=20):
            assert current_user.id == user1.id
            return PageResponse(items=[], total=0, page=1, page_size=20, total_pages=0)

        monkeypatch.setattr(BaselineService, "list_baselines", fake_list)
        resp = client.get("/api/baselines", headers=auth_header(user1.id, user1.username))
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_get_baseline_200(self, client, monkeypatch, user1):
        async def fake_get(self, baseline_id, current_user):
            from tests.conftest import make_baseline
            from app.schemas.baseline import BaselineDetailDTO
            b = make_baseline(baseline_id=baseline_id, owner_id=current_user.id, report={"components": []})
            return BaselineDetailDTO(
                id=b.id, name=b.name, description=b.description,
                source_task_id=b.source_task_id, source_task_name="",
                language=b.language, code_path=b.code_path, asset_count=b.asset_count,
                created_by=b.created_by, creator_name="owner",
                created_at=b.created_at, report={"components": []},
            )

        monkeypatch.setattr(BaselineService, "get_baseline", fake_get)
        resp = client.get("/api/baselines/5", headers=auth_header(user1.id, user1.username))
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 5

    def test_create_baseline_200(self, client, monkeypatch, user1):
        captured = {}

        async def fake_create(self, req, current_user):
            captured["user_id"] = current_user.id
            captured["name"] = req.name
            from tests.conftest import make_baseline
            b = make_baseline(baseline_id=9, owner_id=current_user.id, report={"components": []})
            from app.schemas.baseline import BaselineDetailDTO
            return BaselineDetailDTO(
                id=b.id, name=req.name, description="", source_task_id=req.task_id,
                source_task_name="", language=b.language, code_path=b.code_path,
                asset_count=0, created_by=current_user.id, creator_name="alice",
                created_at=b.created_at, report={"components": []},
            )

        monkeypatch.setattr(BaselineService, "create_baseline", fake_create)
        resp = client.post(
            "/api/baselines",
            json={"name": "release-v1", "description": "", "task_id": 3},
            headers=auth_header(user1.id, user1.username),
        )
        assert resp.status_code == 200
        assert captured["name"] == "release-v1"
        assert captured["user_id"] == user1.id

    def test_delete_baseline_owner_200(self, client, monkeypatch, user1):
        async def fake_delete(self, baseline_id, current_user):
            return True

        monkeypatch.setattr(BaselineService, "delete_baseline", fake_delete)
        resp = client.delete("/api/baselines/4", headers=auth_header(user1.id, user1.username))
        assert resp.status_code == 200

    def test_create_diff_200(self, client, monkeypatch, user1):
        async def fake_create_diff(self, baseline_id, task_id, current_user):
            from tests.conftest import make_diff
            d = make_diff(diff_id=21, owner_id=current_user.id, baseline_id=baseline_id, task_id=task_id)
            from app.schemas.baseline import DiffDetailDTO
            return DiffDetailDTO(
                id=d.id, baseline_id=d.baseline_id, baseline_name="b",
                task_id=d.task_id, task_name="t", added_count=1, removed_count=0,
                changed_count=0, unchanged_count=0, risk_level="low",
                created_by=current_user.id, creator_name="alice", created_at=d.created_at,
                diff={"summary": {"added": 1, "removed": 0, "changed": 0}},
            )

        monkeypatch.setattr(BaselineService, "create_diff", fake_create_diff)
        resp = client.post(
            "/api/diffs",
            json={"baseline_id": 1, "task_id": 2},
            headers=auth_header(user1.id, user1.username),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 21
        assert resp.json()["data"]["added_count"] == 1

    def test_get_diff_200(self, client, monkeypatch, user1):
        async def fake_get_diff(self, diff_id, current_user):
            from tests.conftest import make_diff
            d = make_diff(diff_id=diff_id, owner_id=current_user.id)
            from app.schemas.baseline import DiffDetailDTO
            return DiffDetailDTO(
                id=d.id, baseline_id=d.baseline_id, baseline_name="b",
                task_id=d.task_id, task_name="t", added_count=0, removed_count=0,
                changed_count=0, unchanged_count=0, risk_level="none",
                created_by=current_user.id, creator_name="alice", created_at=d.created_at,
                diff={"summary": {}},
            )

        monkeypatch.setattr(BaselineService, "get_diff", fake_get_diff)
        resp = client.get("/api/diffs/7", headers=auth_header(user1.id, user1.username))
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 7

    def test_list_diffs_200(self, client, monkeypatch, user1):
        async def fake_list(self, task_id, current_user):
            assert task_id == 3
            return []

        monkeypatch.setattr(BaselineService, "list_diffs_by_task", fake_list)
        resp = client.get(
            "/api/diffs", params={"task_id": 3},
            headers=auth_header(user1.id, user1.username),
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Business errors propagated from service → HTTP status codes
# ---------------------------------------------------------------------------

class TestBusinessErrorMapping:
    def test_cross_user_returns_403(self, client, monkeypatch, user1):
        async def fake_get(self, baseline_id, current_user):
            raise ForbiddenException("无权访问或操作此基线")

        monkeypatch.setattr(BaselineService, "get_baseline", fake_get)
        resp = client.get("/api/baselines/1", headers=auth_header(user1.id, user1.username))
        assert resp.status_code == 403
        body = resp.json()
        assert body["code"] == 403
        assert "无权" in body["message"]

    def test_cross_project_returns_403(self, client, monkeypatch, user1):
        async def fake_create_diff(self, baseline_id, task_id, current_user):
            raise ForbiddenException("基线与当前分析不属于同一项目，无法生成差异")

        monkeypatch.setattr(BaselineService, "create_diff", fake_create_diff)
        resp = client.post(
            "/api/diffs",
            json={"baseline_id": 1, "task_id": 2},
            headers=auth_header(user1.id, user1.username),
        )
        assert resp.status_code == 403
        assert "同一项目" in resp.json()["message"]

    def test_not_found_returns_404(self, client, monkeypatch, user1):
        async def fake_get(self, baseline_id, current_user):
            raise NotFoundException("Baseline not found: 999")

        monkeypatch.setattr(BaselineService, "get_baseline", fake_get)
        resp = client.get("/api/baselines/999", headers=auth_header(user1.id, user1.username))
        assert resp.status_code == 404
        assert resp.json()["code"] == 404

    def test_delete_not_found_returns_404(self, client, monkeypatch, user1):
        async def fake_delete(self, baseline_id, current_user):
            return False

        monkeypatch.setattr(BaselineService, "delete_baseline", fake_delete)
        resp = client.delete("/api/baselines/999", headers=auth_header(user1.id, user1.username))
        assert resp.status_code == 200
        assert resp.json()["code"] == 404

    def test_validation_error_returns_400(self, client, monkeypatch, user1):
        async def fake_create(self, req, current_user):
            raise ValueError("只能基于已完成且有结果的分析任务创建基线")

        monkeypatch.setattr(BaselineService, "create_baseline", fake_create)
        resp = client.post(
            "/api/baselines",
            json={"name": "x", "task_id": 1},
            headers=auth_header(user1.id, user1.username),
        )
        assert resp.status_code == 400
        assert "已完成" in resp.json()["message"]

    def test_create_baseline_validation_error_body(self, client):
        resp = client.post(
            "/api/baselines",
            json={"name": "", "task_id": 1},
            headers=auth_header(1),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Admin role is correctly conveyed to the service — but does NOT bypass ownership
# ---------------------------------------------------------------------------

class TestAdminStrictOwnership:
    def test_admin_token_passes_admin_role(self, client, monkeypatch):
        seen = {}

        async def fake_list(self, current_user, page=1, page_size=20):
            seen["role"] = current_user.role
            seen["user_id"] = current_user.id
            return PageResponse(items=[], total=0, page=1, page_size=20, total_pages=0)

        monkeypatch.setattr(BaselineService, "list_baselines", fake_list)
        resp = client.get("/api/baselines", headers=auth_header(99, "admin", "admin"))
        assert resp.status_code == 200
        assert seen["role"] == "admin"
        assert seen["user_id"] == 99

    def test_admin_get_other_users_baseline_returns_403(self, client, monkeypatch):
        """管理员访问他人基线也返回 403。"""
        async def fake_get(self, baseline_id, current_user):
            raise ForbiddenException("无权访问或操作此基线")

        monkeypatch.setattr(BaselineService, "get_baseline", fake_get)
        resp = client.get(
            "/api/baselines/5",
            headers=auth_header(99, "admin", "admin"),
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == 403

    def test_admin_create_baseline_from_other_users_task_returns_403(self, client, monkeypatch):
        """管理员基于他人任务创建基线返回 403。"""
        async def fake_create(self, req, current_user):
            raise ForbiddenException("无权访问或操作此来源分析任务")

        monkeypatch.setattr(BaselineService, "create_baseline", fake_create)
        resp = client.post(
            "/api/baselines",
            json={"name": "x", "task_id": 10},
            headers=auth_header(99, "admin", "admin"),
        )
        assert resp.status_code == 403

    def test_admin_delete_other_users_baseline_returns_403(self, client, monkeypatch):
        """管理员删除他人基线返回 403。"""
        async def fake_delete(self, baseline_id, current_user):
            raise ForbiddenException("无权访问或操作此基线")

        monkeypatch.setattr(BaselineService, "delete_baseline", fake_delete)
        resp = client.delete(
            "/api/baselines/5",
            headers=auth_header(99, "admin", "admin"),
        )
        assert resp.status_code == 403

    def test_admin_create_diff_for_other_users_resources_returns_403(self, client, monkeypatch):
        """管理员用他人资源生成差异返回 403。"""
        async def fake_create_diff(self, baseline_id, task_id, current_user):
            raise ForbiddenException("无权访问或操作此基线")

        monkeypatch.setattr(BaselineService, "create_diff", fake_create_diff)
        resp = client.post(
            "/api/diffs",
            json={"baseline_id": 1, "task_id": 2},
            headers=auth_header(99, "admin", "admin"),
        )
        assert resp.status_code == 403

    def test_admin_get_other_users_diff_returns_403(self, client, monkeypatch):
        """管理员查看他人差异返回 403。"""
        async def fake_get_diff(self, diff_id, current_user):
            raise ForbiddenException("无权访问或操作此差异报告")

        monkeypatch.setattr(BaselineService, "get_diff", fake_get_diff)
        resp = client.get(
            "/api/diffs/7",
            headers=auth_header(99, "admin", "admin"),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cross-project via project_key (including temp-path / upload scenarios)
# ---------------------------------------------------------------------------

class TestCrossProjectViaProjectKey:
    def test_temp_path_cross_project_returns_403(self, client, monkeypatch, user1):
        """上传临时路径但 project_key 不同 → 403。"""
        async def fake_create_diff(self, baseline_id, task_id, current_user):
            raise ForbiddenException(
                "基线与当前分析不属于同一项目，无法生成差异（项目标识: alpha ≠ beta）"
            )

        monkeypatch.setattr(BaselineService, "create_diff", fake_create_diff)
        resp = client.post(
            "/api/diffs",
            json={"baseline_id": 1, "task_id": 2},
            headers=auth_header(user1.id, user1.username),
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "同一项目" in body["message"]
        assert "alpha" in body["message"]
        assert "beta" in body["message"]

    def test_missing_project_key_returns_403(self, client, monkeypatch, user1):
        """缺少 project_key 时返回 403。"""
        async def fake_create_diff(self, baseline_id, task_id, current_user):
            raise ForbiddenException(
                "基线或当前分析缺少项目标识（project_key），无法判定是否属于同一项目"
            )

        monkeypatch.setattr(BaselineService, "create_diff", fake_create_diff)
        resp = client.post(
            "/api/diffs",
            json={"baseline_id": 1, "task_id": 2},
            headers=auth_header(user1.id, user1.username),
        )
        assert resp.status_code == 403
        assert "project_key" in resp.json()["message"]
