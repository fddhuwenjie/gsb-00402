"""API-level permission tests for baseline endpoints.

Covers unauthenticated access (401) and a regular user attempting an
admin-only delete (403), exercising the real auth dependencies over HTTP.
"""

import json

from app.entities.models import User, UserRole, AnalysisTask, AnalysisResult, TaskStatus


def _report():
    return {
        "cbom_version": "1.0",
        "metadata": {"language": "c"},
        "summary": {"risk_level": "info"},
        "components": [],
    }


async def _seed_baseline(factory):
    """Insert a completed task + result and a baseline; return baseline id."""
    async with factory() as session:
        # Reuse the seeded admin as the creator.
        task = AnalysisTask(
            name="t", language="c", code_path="/app/scans/proj",
            project_key="proj", status=TaskStatus.COMPLETED, created_by=1,
        )
        session.add(task)
        await session.flush()
        session.add(AnalysisResult(
            task_id=task.id, report_json=json.dumps(_report()),
            total_files_scanned=1, total_matches=0, total_components=0, risk_level="info",
        ))
        from app.entities.models import AnalysisBaseline
        baseline = AnalysisBaseline(
            name="v1", description="", task_id=task.id,
            language="c", code_path="/app/scans/proj", project_key="proj",
            report_json=json.dumps(_report()), created_by=1,
        )
        session.add(baseline)
        await session.commit()
        await session.refresh(baseline)
        return baseline.id


class TestBaselinePermissions:
    async def test_list_baselines_requires_auth(self, api_client):
        client = api_client["client"]
        resp = await client.get("/api/baselines")
        assert resp.status_code == 401

    async def test_get_baseline_requires_auth(self, api_client):
        client = api_client["client"]
        resp = await client.get("/api/baselines/1")
        assert resp.status_code == 401

    async def test_create_baseline_requires_auth(self, api_client):
        client = api_client["client"]
        resp = await client.post("/api/baselines", json={"name": "x", "task_id": 1})
        assert resp.status_code == 401

    async def test_delete_baseline_requires_auth(self, api_client):
        client = api_client["client"]
        resp = await client.delete("/api/baselines/1")
        assert resp.status_code == 401

    async def test_invalid_token_rejected(self, api_client):
        client = api_client["client"]
        resp = await client.get("/api/baselines", headers={"Authorization": "Bearer bogus"})
        assert resp.status_code == 401

    async def test_regular_user_cannot_delete_baseline(self, api_client):
        baseline_id = await _seed_baseline(api_client["factory"])
        client = api_client["client"]

        # A regular user is authenticated but lacks admin -> 403, not deleted.
        resp = await client.delete(
            f"/api/baselines/{baseline_id}", headers=api_client["user_headers"]
        )
        assert resp.status_code == 403

        # The baseline is still retrievable by an authenticated user.
        get_resp = await client.get(
            f"/api/baselines/{baseline_id}", headers=api_client["user_headers"]
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == baseline_id

    async def test_regular_user_can_list_and_view(self, api_client):
        """Non-admins retain read access to baselines and diffs."""
        baseline_id = await _seed_baseline(api_client["factory"])
        client = api_client["client"]

        list_resp = await client.get("/api/baselines", headers=api_client["user_headers"])
        assert list_resp.status_code == 200
        assert list_resp.json()["data"]["total"] >= 1

        diffs_resp = await client.get(
            f"/api/baselines/{baseline_id}/diffs", headers=api_client["user_headers"]
        )
        assert diffs_resp.status_code == 200
        assert diffs_resp.json()["data"] == []

    async def test_admin_can_delete_baseline(self, api_client):
        baseline_id = await _seed_baseline(api_client["factory"])
        client = api_client["client"]

        resp = await client.delete(
            f"/api/baselines/{baseline_id}", headers=api_client["admin_headers"]
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Deleted successfully"
