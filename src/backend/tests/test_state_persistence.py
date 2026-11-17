from __future__ import annotations

import asyncio
from pathlib import Path

from dataweave.schemas import (
    CreateRunRequest,
    RunProgress,
    RunSnapshot,
    RunStatus,
    TaskNode,
    TaskStatus,
    UploadResponse,
)
from dataweave.services.run_manager import RunManager
from dataweave.services.state_repository import StateRepository


def test_upload_and_run_survive_repository_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "dataweave.db"
    source_path = tmp_path / "uploads" / "paper.pdf"
    source_path.parent.mkdir()
    source_path.write_bytes(b"%PDF-1.7\npersistent")

    repository = StateRepository(database_path)
    upload = UploadResponse(
        upload_id="upload_persisted",
        document_id="doc_persisted",
        document_version_id="ver_persisted",
        filename="paper.pdf",
        size=source_path.stat().st_size,
        sha256="abc123",
        created_at="2026-11-12T00:00:00+00:00",
    )
    repository.create_upload(upload, source_path)

    request = CreateRunRequest(
        document_id=upload.document_id,
        document_version_id=upload.document_version_id,
        document_name=upload.filename,
    )
    snapshot = RunSnapshot(
        id="run_persisted",
        document_id=upload.document_id,
        document_version_id=upload.document_version_id,
        document_name=upload.filename,
        template_id="paper_analysis",
        template_version=3,
        status=RunStatus.AWAITING_REVIEW,
        created_at="2026-11-12T00:00:00+00:00",
        last_activity_at="2026-11-12T00:00:01+00:00",
        progress=RunProgress(completed=1, total=1, percent=100),
        tasks=[
            TaskNode(
                id="parse",
                name="内容解析",
                kind="parser",
                description="测试",
                executor="MockParser",
                status=TaskStatus.COMPLETED,
            )
        ],
    )
    repository.save_run(snapshot, request, source_path, [{"sequence": 1}], 1)

    reopened = StateRepository(database_path)
    restored_upload = reopened.get_upload(upload.upload_id)
    assert restored_upload is not None
    assert restored_upload.upload.filename == "paper.pdf"
    assert restored_upload.source_path == source_path
    assert reopened.find_document_id_by_sha256("abc123") == "doc_persisted"

    manager = RunManager(reopened)
    restored_run = asyncio.run(manager.get_run("run_persisted"))
    assert restored_run is not None
    assert restored_run.status == "awaiting_review"
    assert restored_run.tasks[0].status == "completed"


def test_running_task_is_recovered_as_interrupted(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "dataweave.db")
    source_path = tmp_path / "paper.pdf"
    source_path.write_bytes(b"%PDF")
    request = CreateRunRequest(
        document_id="doc_active",
        document_version_id="ver_active",
        document_name="active.pdf",
    )
    snapshot = RunSnapshot(
        id="run_active",
        document_id=request.document_id,
        document_version_id=request.document_version_id,
        document_name=request.document_name,
        template_id=request.template_id,
        template_version=request.template_version,
        status=RunStatus.RUNNING,
        created_at="2026-11-12T00:00:00+00:00",
        started_at="2026-11-12T00:00:01+00:00",
        last_activity_at="2026-11-12T00:00:02+00:00",
        progress=RunProgress(completed=0, total=2, percent=0, current_task="解析"),
        tasks=[
            TaskNode(
                id="parse",
                name="解析",
                kind="parser",
                description="测试",
                executor="MockParser",
                status=TaskStatus.RUNNING,
                children=[
                    TaskNode(
                        id="persist",
                        name="保存",
                        kind="artifact",
                        description="测试",
                        executor="LocalStore",
                        status=TaskStatus.PENDING,
                    )
                ],
            )
        ],
    )
    repository.save_run(snapshot, request, source_path, [], 0)

    manager = RunManager(StateRepository(repository.database_path))
    restored = asyncio.run(manager.get_run("run_active"))
    assert restored is not None
    assert restored.status == "failed"
    assert restored.progress.current_task is None
    assert restored.tasks[0].status == "failed"
    assert restored.tasks[0].children[0].status == "cancelled"
    assert restored.tasks[0].output["interrupted_by_restart"] is True

    persisted = StateRepository(repository.database_path).list_runs()[0]
    assert persisted.snapshot.status == "failed"
    assert persisted.events[-1]["type"] == "run.interrupted"
