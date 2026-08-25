"""Integration tests for BaselineService — baseline creation, diff generation,
no-baseline errors, empty results and consistency checks (uses in-memory SQLite)."""

import json

import pytest

from app.entities.models import (
    User, UserRole, AnalysisTask, AnalysisResult, TaskStatus,
)
from app.schemas.baseline import BaselineCreateRequest, DiffGenerateRequest
from app.services.baseline_service import BaselineService


def _report(language, components):
    return {
        "cbom_version": "1.0",
        "metadata": {"language": language},
        "summary": {"risk_level": "info"},
        "components": components,
    }


def _component(name, library_key, functions):
    return {"name": name, "library_key": library_key, "type": "tls_library", "functions": functions}


def _func(signature, files):
    return {
        "signature": signature,
        "match_type": "exact",
        "best_confidence": 1.0,
        "locations": [{"file": f, "line": 1, "matched_text": "x", "confidence": 1.0, "context": ""} for f in files],
    }


async def _seed_user(session):
    user = User(username="tester", password_hash="x", role=UserRole.USER)
    session.add(user)
    await session.flush()
    return user


async def _seed_task(session, user_id, language="c", code_path="/app/scans/proj", report=None,
                     status=TaskStatus.COMPLETED, name="task", project_key=None):
    task = AnalysisTask(
        name=name, language=language, code_path=code_path,
        project_key=project_key or code_path,
        status=status, created_by=user_id,
    )
    session.add(task)
    await session.flush()
    if report is not None:
        result = AnalysisResult(
            task_id=task.id,
            report_json=json.dumps(report, ensure_ascii=False),
            total_files_scanned=1,
            total_matches=1,
            total_components=len(report.get("components", [])),
            risk_level=report["summary"]["risk_level"],
        )
        session.add(result)
        await session.flush()
    return task


class TestBaselineService:
    async def test_create_baseline_and_generate_diff(self, db_session):
        user = await _seed_user(db_session)
        base_report = _report("c", [
            _component("Mbed TLS", "mbedtls", [_func("mbedtls_ssl_read", ["a.c"])]),
        ])
        new_report = _report("c", [
            _component("Mbed TLS", "mbedtls", [_func("mbedtls_ssl_read", ["a.c"])]),
            _component("OpenSSL", "openssl", [_func("openssl_encrypt", ["b.c"])]),
        ])
        base_task = await _seed_task(db_session, user.id, report=base_report, name="base")
        new_task = await _seed_task(db_session, user.id, report=new_report, name="new")
        await db_session.commit()

        service = BaselineService(db_session)
        baseline = await service.create_baseline(
            BaselineCreateRequest(name="v1", task_id=base_task.id), user.id
        )
        assert baseline.id > 0
        assert baseline.language == "c"

        diff_dto = await service.generate_diff(
            baseline.id, DiffGenerateRequest(task_id=new_task.id), user.id
        )
        assert diff_dto.total_added == 1
        assert diff_dto.total_removed == 0
        assert diff_dto.total_changed == 0
        assert diff_dto.diff["added"][0]["signature"] == "openssl_encrypt"

    async def test_generate_diff_no_baseline(self, db_session):
        """Generating a diff against a non-existent baseline raises an error."""
        user = await _seed_user(db_session)
        task = await _seed_task(db_session, user.id, report=_report("c", []))
        await db_session.commit()

        service = BaselineService(db_session)
        with pytest.raises(ValueError, match="基线不存在"):
            await service.generate_diff(9999, DiffGenerateRequest(task_id=task.id), user.id)

    async def test_get_diff_no_report(self, db_session):
        service = BaselineService(db_session)
        with pytest.raises(ValueError, match="差异报告不存在"):
            await service.get_diff(1234)

    async def test_generate_diff_empty_result(self, db_session):
        """Identical baseline and analysis produce an empty (zero) diff."""
        user = await _seed_user(db_session)
        report = _report("c", [
            _component("Mbed TLS", "mbedtls", [_func("mbedtls_ssl_read", ["a.c"])]),
        ])
        base_task = await _seed_task(db_session, user.id, report=report, name="base")
        # A separate completed task with an identical report.
        new_task = await _seed_task(db_session, user.id, report=report, name="new")
        await db_session.commit()

        service = BaselineService(db_session)
        baseline = await service.create_baseline(
            BaselineCreateRequest(name="v1", task_id=base_task.id), user.id
        )
        diff_dto = await service.generate_diff(
            baseline.id, DiffGenerateRequest(task_id=new_task.id), user.id
        )
        assert diff_dto.total_added == 0
        assert diff_dto.total_removed == 0
        assert diff_dto.total_changed == 0
        assert diff_dto.diff["added"] == []
        assert diff_dto.diff["by_file"] == {}

    async def test_baseline_requires_completed_task(self, db_session):
        user = await _seed_user(db_session)
        task = await _seed_task(db_session, user.id, status=TaskStatus.RUNNING, report=None)
        await db_session.commit()

        service = BaselineService(db_session)
        with pytest.raises(ValueError, match="只能为已完成"):
            await service.create_baseline(
                BaselineCreateRequest(name="v1", task_id=task.id), user.id
            )

    async def test_diff_rejects_inconsistent_language(self, db_session):
        user = await _seed_user(db_session)
        base_task = await _seed_task(db_session, user.id, language="c",
                                     code_path="/app/scans/proj", report=_report("c", []))
        # Same path but different language.
        other_task = await _seed_task(db_session, user.id, language="python",
                                      code_path="/app/scans/proj", report=_report("python", []))
        await db_session.commit()

        service = BaselineService(db_session)
        baseline = await service.create_baseline(
            BaselineCreateRequest(name="v1", task_id=base_task.id), user.id
        )
        with pytest.raises(ValueError, match="语言与基线不一致"):
            await service.generate_diff(
                baseline.id, DiffGenerateRequest(task_id=other_task.id), user.id
            )

    async def test_diff_rejects_different_project(self, db_session):
        """Tasks with different project keys cannot be compared."""
        user = await _seed_user(db_session)
        base_task = await _seed_task(db_session, user.id, project_key="proj-a",
                                     code_path="/tmp/upload-1", report=_report("c", []))
        other_task = await _seed_task(db_session, user.id, project_key="proj-b",
                                      code_path="/tmp/upload-2", report=_report("c", []))
        await db_session.commit()

        service = BaselineService(db_session)
        baseline = await service.create_baseline(
            BaselineCreateRequest(name="v1", task_id=base_task.id), user.id
        )
        with pytest.raises(ValueError, match="不属于同一项目"):
            await service.generate_diff(
                baseline.id, DiffGenerateRequest(task_id=other_task.id), user.id
            )

    async def test_uploaded_project_diff_across_temp_dirs(self, db_session):
        """Two uploads of the same project (different temp dirs, same project_key)
        must be comparable — this is the core upload-baseline fix."""
        user = await _seed_user(db_session)
        # First upload: baseline snapshot from a throwaway temp directory.
        base_task = await _seed_task(
            db_session, user.id, name="upload-1", project_key="my-service",
            code_path="/tmp/cbom_scan_aaa",
            report=_report("c", [
                _component("Mbed TLS", "mbedtls", [_func("mbedtls_ssl_read", ["a.c"])]),
            ]),
        )
        # Second upload of the SAME project lands in a DIFFERENT temp directory.
        new_task = await _seed_task(
            db_session, user.id, name="upload-2", project_key="my-service",
            code_path="/tmp/cbom_scan_bbb",
            report=_report("c", [
                _component("Mbed TLS", "mbedtls", [_func("mbedtls_ssl_read", ["a.c"])]),
                _component("OpenSSL", "openssl", [_func("openssl_encrypt", ["b.c"])]),
            ]),
        )
        await db_session.commit()

        service = BaselineService(db_session)
        baseline = await service.create_baseline(
            BaselineCreateRequest(name="v1", task_id=base_task.id), user.id
        )
        assert baseline.project_key == "my-service"
        # Despite differing code paths, the diff succeeds and detects the new asset.
        assert base_task.code_path != new_task.code_path
        diff_dto = await service.generate_diff(
            baseline.id, DiffGenerateRequest(task_id=new_task.id), user.id
        )
        assert diff_dto.total_added == 1
        assert diff_dto.diff["added"][0]["signature"] == "openssl_encrypt"

    async def test_baseline_has_assets_new_empty(self, db_session):
        """Baseline with crypto assets vs. a later empty analysis -> all removed."""
        user = await _seed_user(db_session)
        base_task = await _seed_task(db_session, user.id, name="base", report=_report("c", [
            _component("Mbed TLS", "mbedtls", [_func("mbedtls_ssl_read", ["a.c"])]),
        ]))
        empty_task = await _seed_task(db_session, user.id, name="empty", report=_report("c", []))
        await db_session.commit()

        service = BaselineService(db_session)
        baseline = await service.create_baseline(
            BaselineCreateRequest(name="v1", task_id=base_task.id), user.id
        )
        diff_dto = await service.generate_diff(
            baseline.id, DiffGenerateRequest(task_id=empty_task.id), user.id
        )
        assert diff_dto.total_removed == 1
        assert diff_dto.total_added == 0
        assert diff_dto.total_changed == 0
        assert diff_dto.diff["removed"][0]["signature"] == "mbedtls_ssl_read"

    async def test_regenerate_diff_overwrites(self, db_session):
        """Re-generating a diff for the same baseline+task overwrites the old one."""
        user = await _seed_user(db_session)
        base_task = await _seed_task(db_session, user.id, report=_report("c", []), name="base")
        new_task = await _seed_task(db_session, user.id, report=_report("c", [
            _component("OpenSSL", "openssl", [_func("openssl_encrypt", ["b.c"])]),
        ]), name="new")
        await db_session.commit()

        service = BaselineService(db_session)
        baseline = await service.create_baseline(
            BaselineCreateRequest(name="v1", task_id=base_task.id), user.id
        )
        first = await service.generate_diff(baseline.id, DiffGenerateRequest(task_id=new_task.id), user.id)
        second = await service.generate_diff(baseline.id, DiffGenerateRequest(task_id=new_task.id), user.id)

        assert first.id == second.id
        diffs = await service.list_diffs(baseline.id)
        assert len(diffs) == 1
