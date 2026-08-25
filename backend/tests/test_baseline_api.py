"""
Interface tests for baseline & diff endpoints.

Covers the business boundaries:
- unauthenticated access is rejected (401)
- regular users cannot read/use other users' baselines/diffs/tasks (403),
  while admins see everything
- diffs across different code projects are rejected (400); the project
  identity is the normalized code path
- empty results (no data for a user, identical reports -> zero diff)

Persistence is replaced by in-memory repositories; the real service,
diff engine, auth dependencies, routing and exception handlers run.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/cbom_test")
os.environ.setdefault("SECRET_KEY", "test-secret")

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.controllers.deps import get_current_user, require_admin, CurrentUser
from app.entities.models import TaskStatus
from app.core.cbom_generator import CBOMGenerator
from app.core.fuzzy_matcher import MatchResult, MatchType
from app.services import baseline_service

PROJ_A = "/tmp/cbom-proj-a"
PROJ_B = "/tmp/cbom-proj-b"

ADMIN = CurrentUser(id=1, username="admin", role="admin")
ALICE = CurrentUser(id=2, username="alice", role="user")
BOB = CurrentUser(id=3, username="bob", role="user")


# ---------------- in-memory fakes ----------------

class FakeDB:
    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def flush(self):
        pass

    def expire_all(self):
        pass


class FakeStore:
    def __init__(self):
        self.baselines = []
        self.diffs = []
        self.tasks = {}
        self._baseline_seq = 0
        self._diff_seq = 0
        self.usernames = {1: "admin", 2: "alice", 3: "bob"}

    def creator(self, user_id):
        return SimpleNamespace(username=self.usernames.get(user_id, f"user{user_id}"))


class FakeBaselineRepository:
    store = None

    def __init__(self, db=None):
        pass

    async def find_all(self, page=1, page_size=20, created_by=None):
        items = sorted(self.store.baselines, key=lambda b: b.id, reverse=True)
        if created_by is not None:
            items = [b for b in items if b.created_by == created_by]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def find_by_id(self, baseline_id):
        return next((b for b in self.store.baselines if b.id == baseline_id), None)

    async def create(self, baseline):
        self.store._baseline_seq += 1
        record = SimpleNamespace(
            id=self.store._baseline_seq,
            name=baseline.name,
            description=baseline.description,
            task_id=baseline.task_id,
            language=baseline.language,
            snapshot_json=baseline.snapshot_json,
            total_assets=baseline.total_assets,
            risk_level=baseline.risk_level,
            created_by=baseline.created_by,
            created_at=datetime.utcnow(),
            task=self.store.tasks.get(baseline.task_id),
            creator=self.store.creator(baseline.created_by),
        )
        self.store.baselines.append(record)
        return record

    async def delete_by_id(self, baseline_id):
        for i, b in enumerate(self.store.baselines):
            if b.id == baseline_id:
                self.store.baselines.pop(i)
                return True
        return False


class FakeDiffReportRepository:
    store = None

    def __init__(self, db=None):
        pass

    async def find_all(self, page=1, page_size=20, created_by=None):
        items = sorted(self.store.diffs, key=lambda d: d.id, reverse=True)
        if created_by is not None:
            items = [d for d in items if d.created_by == created_by]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def find_by_id(self, diff_id):
        return next((d for d in self.store.diffs if d.id == diff_id), None)

    async def create(self, diff_report):
        self.store._diff_seq += 1
        record = SimpleNamespace(
            id=self.store._diff_seq,
            name=diff_report.name,
            baseline_id=diff_report.baseline_id,
            task_id=diff_report.task_id,
            diff_json=diff_report.diff_json,
            added_count=diff_report.added_count,
            removed_count=diff_report.removed_count,
            changed_count=diff_report.changed_count,
            risk_level=diff_report.risk_level,
            created_by=diff_report.created_by,
            created_at=datetime.utcnow(),
            baseline=next((b for b in self.store.baselines if b.id == diff_report.baseline_id), None),
            task=self.store.tasks.get(diff_report.task_id),
            creator=self.store.creator(diff_report.created_by),
        )
        self.store.diffs.append(record)
        return record

    async def delete_by_id(self, diff_id):
        for i, d in enumerate(self.store.diffs):
            if d.id == diff_id:
                self.store.diffs.pop(i)
                return True
        return False


class FakeAnalysisRepository:
    store = None

    def __init__(self, db=None):
        pass

    async def find_by_id(self, task_id):
        return self.store.tasks.get(task_id)


# ---------------- helpers ----------------

def _match(signature, file_path, line):
    return MatchResult(
        signature_pattern=signature,
        matched_text=signature,
        match_type=MatchType.EXACT,
        confidence=1.0,
        file_path=file_path,
        line_number=line,
        context=f"{signature}(...);",
    )


def make_task(store, tid, name, code_path, owner, signatures=(), language="c"):
    """Register a completed analysis task with a real CBOM report payload."""
    gen = CBOMGenerator()
    matches = [_match(sig, f"src/{sig}.c", i + 1) for i, sig in enumerate(signatures)]
    report = gen.generate(matches, code_path, language, ["sigs.yar"], max(len(matches), 1), 0.01)
    task = SimpleNamespace(
        id=tid,
        name=name,
        language=language,
        code_path=str(Path(code_path).resolve()),
        status=TaskStatus.COMPLETED,
        created_by=owner,
        result=SimpleNamespace(report_json=json.dumps(report)),
    )
    store.tasks[tid] = task
    return task


@pytest.fixture
def ctx(monkeypatch):
    store = FakeStore()
    FakeBaselineRepository.store = store
    FakeDiffReportRepository.store = store
    FakeAnalysisRepository.store = store

    monkeypatch.setattr(baseline_service, "BaselineRepository", FakeBaselineRepository)
    monkeypatch.setattr(baseline_service, "DiffReportRepository", FakeDiffReportRepository)
    monkeypatch.setattr(baseline_service, "AnalysisRepository", FakeAnalysisRepository)

    async def _get_db():
        yield FakeDB()

    state = {"user": ALICE}

    def _current_user():
        return state["user"]

    def _require_admin():
        if state["user"].role != "admin":
            raise HTTPException(status_code=403, detail="Admin privileges required")
        return state["user"]

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[require_admin] = _require_admin

    # NOTE: instantiated without a context manager on purpose so the app
    # lifespan (DB init / storage dir creation) does not run.
    client = TestClient(app)
    try:
        yield SimpleNamespace(
            client=client,
            store=store,
            set_user=lambda u: state.__setitem__("user", u),
        )
    finally:
        app.dependency_overrides.clear()


def create_baseline(client, task_id, name="baseline"):
    return client.post("/api/baselines", json={"name": name, "task_id": task_id})


def create_diff(client, baseline_id, task_id, name=""):
    return client.post("/api/diffs", json={"name": name, "baseline_id": baseline_id, "task_id": task_id})


# ---------------- unauthenticated ----------------

class TestUnauthenticated:
    def test_endpoints_require_login(self, ctx):
        # simulate a request without any logged-in user
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(require_admin, None)
        c = ctx.client

        assert c.get("/api/baselines").status_code == 401
        assert c.post("/api/baselines", json={"name": "x", "task_id": 1}).status_code == 401
        assert c.get("/api/baselines/1").status_code == 401
        assert c.get("/api/diffs").status_code == 401
        assert c.post("/api/diffs", json={"baseline_id": 1, "task_id": 1}).status_code == 401
        assert c.get("/api/diffs/1").status_code == 401
        # delete requires admin auth first -> 401, not 403
        assert c.delete("/api/baselines/1").status_code == 401
        assert c.delete("/api/diffs/1").status_code == 401


# ---------------- permission scope ----------------

class TestPermissionScope:
    def test_user_cannot_baseline_other_users_task(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "alice-scan", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])

        ctx.set_user(BOB)
        resp = create_baseline(ctx.client, 1)
        assert resp.status_code == 403
        assert "无权" in resp.json()["message"]

    def test_user_cannot_read_other_users_baseline(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "alice-scan", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]

        ctx.set_user(BOB)
        resp = ctx.client.get(f"/api/baselines/{bid}")
        assert resp.status_code == 403

    def test_user_cannot_diff_against_other_users_baseline(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "alice-scan", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]

        ctx.set_user(BOB)
        make_task(store, 2, "bob-scan", PROJ_B, BOB.id, ["mbedtls_ssl_read"])
        resp = create_diff(ctx.client, bid, 2)
        assert resp.status_code == 403

    def test_user_cannot_read_other_users_diff(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "alice-scan-a", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        make_task(store, 2, "alice-scan-a2", PROJ_A, ALICE.id, ["mbedtls_ssl_read", "AES_set_encrypt_key"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]
        did = create_diff(ctx.client, bid, 2).json()["data"]["id"]

        ctx.set_user(BOB)
        assert ctx.client.get(f"/api/diffs/{did}").status_code == 403

    def test_non_admin_cannot_delete(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "alice-scan", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]
        make_task(store, 2, "alice-scan-a2", PROJ_A, ALICE.id, ["mbedtls_ssl_read", "AES_set_encrypt_key"])
        did = create_diff(ctx.client, bid, 2).json()["data"]["id"]

        ctx.set_user(BOB)
        assert ctx.client.delete(f"/api/baselines/{bid}").status_code == 403
        assert ctx.client.delete(f"/api/diffs/{did}").status_code == 403

    def test_list_is_scoped_per_user(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "alice-scan", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        create_baseline(ctx.client, 1)

        ctx.set_user(BOB)
        make_task(store, 2, "bob-scan", PROJ_B, BOB.id, ["mbedtls_ssl_read"])
        create_baseline(ctx.client, 2)

        # bob only sees his own baseline
        ctx.set_user(BOB)
        resp = ctx.client.get("/api/baselines")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["created_by"] == BOB.id

        # alice only sees hers
        ctx.set_user(ALICE)
        data = ctx.client.get("/api/baselines").json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["created_by"] == ALICE.id

        # admin sees all
        ctx.set_user(ADMIN)
        data = ctx.client.get("/api/baselines").json()["data"]
        assert data["total"] == 2

    def test_admin_may_access_any_resource(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "alice-scan", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]

        ctx.set_user(ADMIN)
        resp = ctx.client.get(f"/api/baselines/{bid}")
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "baseline"

    def test_missing_resource_returns_404(self, ctx):
        ctx.set_user(BOB)
        assert ctx.client.get("/api/baselines/999").status_code == 404
        assert ctx.client.get("/api/diffs/999").status_code == 404


# ---------------- cross-project boundary ----------------

class TestCrossProject:
    def test_diff_between_different_projects_rejected(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "scan-proj-a", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        make_task(store, 2, "scan-proj-b", PROJ_B, ALICE.id, ["mbedtls_ssl_read"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]

        resp = create_diff(ctx.client, bid, 2)
        assert resp.status_code == 400
        assert "同一个代码项目" in resp.json()["message"]

    def test_admin_cannot_cross_project_either(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "scan-proj-a", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        make_task(store, 2, "scan-proj-b", PROJ_B, ALICE.id, ["mbedtls_ssl_read"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]

        ctx.set_user(ADMIN)
        resp = create_diff(ctx.client, bid, 2)
        assert resp.status_code == 400
        assert "同一个代码项目" in resp.json()["message"]

    def test_same_project_with_normalized_path_allowed(self, ctx):
        """'/tmp/cbom-proj-a/.' resolves to the same project as '/tmp/cbom-proj-a'."""
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "scan-a", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        # different textual path, identical after normalization; one extra crypto asset
        make_task(store, 3, "scan-a-later", f"{PROJ_A}/.", ALICE.id,
                  ["mbedtls_ssl_read", "AES_set_encrypt_key"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]

        resp = create_diff(ctx.client, bid, 3)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["added_count"] == 1
        assert data["removed_count"] == 0
        assert data["risk_level"] == "medium"

    def test_baseline_from_other_users_task_still_blocked_before_project_check(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "alice-a", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]

        # bob owns a task in the SAME path as alice's project; baseline is still not his
        ctx.set_user(BOB)
        make_task(store, 4, "bob-a", PROJ_A, BOB.id, ["mbedtls_ssl_read"])
        resp = create_diff(ctx.client, bid, 4)
        assert resp.status_code == 403


# ---------------- empty results ----------------

class TestEmptyResults:
    def test_lists_are_empty_for_new_user(self, ctx):
        ctx.set_user(BOB)
        baselines = ctx.client.get("/api/baselines").json()["data"]
        assert baselines["items"] == []
        assert baselines["total"] == 0
        assert baselines["total_pages"] == 0

        diffs = ctx.client.get("/api/diffs").json()["data"]
        assert diffs["items"] == []
        assert diffs["total"] == 0

    def test_identical_reports_produce_empty_diff(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        make_task(store, 1, "scan-a-v1", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        make_task(store, 2, "scan-a-v2", PROJ_A, ALICE.id, ["mbedtls_ssl_read"])
        bid = create_baseline(ctx.client, 1).json()["data"]["id"]

        resp = create_diff(ctx.client, bid, 2)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["added_count"] == 0
        assert data["removed_count"] == 0
        assert data["changed_count"] == 0
        assert data["risk_level"] == "none"

        # detail endpoint exposes the empty diff structure
        detail = ctx.client.get(f"/api/diffs/{data['id']}").json()["data"]
        diff = detail["diff"]
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["changed"] == []
        assert diff["summary"]["unchanged"] == 1
        assert diff["categories"]["by_file"] == {}
        assert diff["categories"]["by_language"] == {}
        assert diff["categories"]["by_algorithm"] == {}
        assert diff["categories"]["by_risk_level"] == {}

    def test_baseline_without_crypto_assets(self, ctx):
        store = ctx.store
        ctx.set_user(ALICE)
        # completed scan that found nothing
        make_task(store, 1, "clean-scan", PROJ_A, ALICE.id, signatures=[])
        resp = create_baseline(ctx.client, 1, name="empty-baseline")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_assets"] == 0
        assert data["assets"] == []

        # diffing the empty baseline against another empty scan -> empty result
        make_task(store, 2, "clean-scan-2", PROJ_A, ALICE.id, signatures=[])
        diff_resp = create_diff(ctx.client, data["id"], 2)
        assert diff_resp.status_code == 200
        body = diff_resp.json()["data"]
        assert body["added_count"] == 0 and body["removed_count"] == 0 and body["changed_count"] == 0
        assert body["risk_level"] == "none"
