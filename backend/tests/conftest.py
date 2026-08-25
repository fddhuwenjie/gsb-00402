"""Shared test fixtures for baseline/diff business-validation and API tests."""

import os
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-cbom-tests")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")

from starlette.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.controllers.deps import CurrentUser  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402


def make_token(user_id: int, username: str = "tester", role: str = "user") -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def auth_header(user_id: int, username: str = "tester", role: str = "user") -> dict:
    return {"Authorization": f"Bearer {make_token(user_id, username, role)}"}


def make_task(
    task_id: int = 1,
    owner_id: int = 1,
    language: str = "c",
    code_path: str = "/code/project-a",
    project_key: str | None = None,
    status: str = "completed",
    report: dict | None = None,
):
    from app.entities.models import TaskStatus

    result_obj = None
    if report is not None:
        import json as _json
        result_obj = SimpleNamespace(report_json=_json.dumps(report))

    return SimpleNamespace(
        id=task_id,
        name=f"task-{task_id}",
        language=language,
        code_path=code_path,
        project_key=project_key if project_key is not None else code_path,
        status=TaskStatus.COMPLETED if status == "completed" else TaskStatus.PENDING,
        created_by=owner_id,
        result=result_obj,
        created_at=datetime.datetime.utcnow(),
    )


def make_baseline(
    baseline_id: int = 1,
    owner_id: int = 1,
    language: str = "c",
    code_path: str = "/code/project-a",
    project_key: str | None = None,
    report: dict | None = None,
):
    import json as _json
    return SimpleNamespace(
        id=baseline_id,
        name=f"baseline-{baseline_id}",
        description="",
        source_task_id=1,
        language=language,
        code_path=code_path,
        project_key=project_key if project_key is not None else code_path,
        report_json=_json.dumps(report or {"components": [], "metadata": {"language": language}}),
        asset_count=0,
        created_by=owner_id,
        creator=SimpleNamespace(username="owner"),
        created_at=datetime.datetime.utcnow(),
    )


def make_diff(
    diff_id: int = 1,
    owner_id: int = 1,
    baseline_id: int = 1,
    task_id: int = 1,
    diff: dict | None = None,
):
    import json as _json
    return SimpleNamespace(
        id=diff_id,
        baseline_id=baseline_id,
        task_id=task_id,
        diff_json=_json.dumps(diff or {"summary": {"added": 0, "removed": 0, "changed": 0, "unchanged": 0, "risk_level": "none"}}),
        added_count=0,
        removed_count=0,
        changed_count=0,
        unchanged_count=0,
        risk_level="none",
        created_by=owner_id,
        creator=SimpleNamespace(username="owner"),
        baseline=SimpleNamespace(name=f"baseline-{baseline_id}"),
        task=SimpleNamespace(name=f"task-{task_id}"),
        created_at=datetime.datetime.utcnow(),
    )


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def service(mock_db):
    from app.services.baseline_service import BaselineService

    svc = BaselineService(mock_db)
    svc.repo = AsyncMock()
    svc.analysis_repo = AsyncMock()
    return svc


@pytest.fixture
def client():
    """TestClient that does NOT trigger the lifespan (no DB required)."""
    from unittest.mock import MagicMock

    async def _override_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def user1():
    return CurrentUser(id=1, username="alice", role="user")


@pytest.fixture
def user2():
    return CurrentUser(id=2, username="bob", role="user")


@pytest.fixture
def admin():
    return CurrentUser(id=99, username="admin", role="admin")
