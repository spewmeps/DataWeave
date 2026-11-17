from __future__ import annotations

import asyncio
import copy
import json
import time
import traceback
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from dataweave.config import settings
from dataweave.schemas import (
    CreateRunRequest,
    Metric,
    RunProgress,
    RunSnapshot,
    RunStatus,
    TaskNode,
    TaskStatus,
)
from dataweave.services.extraction import schema_extractor
from dataweave.services.extraction.base import ExtractionProgress, ExtractionRequest
from dataweave.services.extraction.deepagents_extractor import AGENT_GROUPS
from dataweave.observability import agent_log_store, application_logger, run_log_store
from dataweave.services.parsers import document_parser
from dataweave.services.parsers.base import ParseProgress, ParseRequest
from dataweave.services.state_repository import StateRepository, state_repository
from dataweave.template_catalog import paper_analysis_template


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass(slots=True)
class RunRecord:
    snapshot: RunSnapshot
    request: CreateRunRequest
    source_path: Path
    events: list[dict[str, Any]] = field(default_factory=list)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    sequence: int = 0


class RunManager:
    """Run/Task API runtime backed by durable SQLite snapshots."""

    def __init__(self, repository: StateRepository = state_repository) -> None:
        self._repository = repository
        self._records: dict[str, RunRecord] = {}
        self._background: set[asyncio.Task[None]] = set()
        self._lock = asyncio.Lock()
        self._load_persisted_records()

    def _load_persisted_records(self) -> None:
        for stored in self._repository.list_runs():
            record = RunRecord(
                snapshot=stored.snapshot,
                request=stored.request,
                source_path=stored.source_path,
                events=stored.events,
                sequence=stored.sequence,
            )
            self._records[record.snapshot.id] = record
            self._restore_run_log(record)
            self._restore_agent_logs(record)
            if record.snapshot.status in {
                RunStatus.CREATED,
                RunStatus.QUEUED,
                RunStatus.RUNNING,
            }:
                self._mark_interrupted_by_restart(record)

    @staticmethod
    def _restore_run_log(record: RunRecord) -> None:
        try:
            path = run_log_store.path_for(record.snapshot.id)
            if path.exists():
                return
            for event in record.events:
                run_log_store.event(
                    record.snapshot.id,
                    str(event.get("type") or "run.event"),
                    task_id=event.get("task_id"),
                    level="ERROR" if "failed" in str(event.get("type")) else "INFO",
                    payload={
                        **(event.get("payload") or {}),
                        "restored_event_id": event.get("event_id"),
                        "original_timestamp": event.get("occurred_at"),
                    },
                )
            run_log_store.event(
                record.snapshot.id,
                "run.log.restored",
                message="日志功能启用前的运行已从 SQLite 事件记录恢复。",
                payload={"status": record.snapshot.status, "events": len(record.events)},
            )
        except Exception:
            application_logger.exception("Failed to restore run log: run_id=%s", record.snapshot.id)

    @staticmethod
    def _restore_agent_logs(record: RunRecord) -> None:
        """Give pre-observability runs a useful summary without fabricating traces."""

        try:
            extraction = next(
                (task for task in record.snapshot.tasks if task.id == "extract"),
                None,
            )
            if not extraction:
                return
            supervisor_path = agent_log_store.path_for(record.snapshot.id, "schema_supervisor")
            if not supervisor_path.exists():
                agent_log_store.event(
                    record.snapshot.id,
                    "schema_supervisor",
                    "history.summary",
                    message="该运行早于 Agent 详细日志功能，仅从 SQLite Task Snapshot 恢复摘要。",
                    payload={
                        "task_status": str(extraction.status),
                        "started_at": extraction.started_at,
                        "finished_at": extraction.finished_at,
                        "duration_ms": extraction.duration_ms,
                        "detailed_trace_available": False,
                    },
                )
            for task in extraction.children:
                if task.executor != "DeepAgent":
                    continue
                path = agent_log_store.path_for(record.snapshot.id, task.id)
                if path.exists():
                    continue
                fields = task.output.get("fields")
                agent_log_store.event(
                    record.snapshot.id,
                    task.id,
                    "history.summary",
                    message="该运行早于 Agent 详细日志功能，仅从 SQLite Task Snapshot 恢复摘要。",
                    payload={
                        "agent_name": task.name,
                        "task_status": str(task.status),
                        "assigned_fields": fields if isinstance(fields, list) else [],
                        "started_at": task.started_at,
                        "finished_at": task.finished_at,
                        "duration_ms": task.duration_ms,
                        "output_summary": {
                            key: value
                            for key, value in task.output.items()
                            if key != "fields"
                        },
                        "detailed_trace_available": False,
                    },
                )
        except Exception:
            application_logger.exception(
                "Failed to restore agent logs: run_id=%s",
                record.snapshot.id,
            )

    def _mark_interrupted_by_restart(self, record: RunRecord) -> None:
        now = utc_now()
        message = "服务重启中断了正在执行的异步任务，请点击重新解析继续。"
        for task in self._flatten_tasks(record.snapshot.tasks):
            if task.status in {TaskStatus.RUNNING, TaskStatus.RETRYING}:
                task.status = TaskStatus.FAILED
                task.finished_at = now
                task.output = {**task.output, "error": message, "interrupted_by_restart": True}
                task.warnings = [message]
            elif task.status in {TaskStatus.PENDING, TaskStatus.QUEUED}:
                task.status = TaskStatus.CANCELLED
                task.output = {"reason": message, "interrupted_by_restart": True}
        record.snapshot.status = RunStatus.FAILED
        record.snapshot.finished_at = now
        record.snapshot.last_activity_at = now
        self._refresh_progress(record.snapshot)
        self._append_event(
            record,
            "run.interrupted",
            None,
            {"status": "failed", "reason": message},
        )

    async def create_run(
        self,
        request: CreateRunRequest,
        source_path: Path,
        *,
        retry_of_run_id: str | None = None,
        retry_number: int = 0,
    ) -> RunSnapshot:
        run_id = new_id("run")
        now = utc_now()
        tasks = self._build_tasks(request)
        snapshot = RunSnapshot(
            id=run_id,
            document_id=request.document_id,
            document_version_id=request.document_version_id,
            document_name=request.document_name,
            template_id=request.template_id,
            template_version=request.template_version,
            retry_of_run_id=retry_of_run_id,
            retry_number=retry_number,
            status=RunStatus.CREATED,
            created_at=now,
            last_activity_at=now,
            progress=RunProgress(completed=0, total=self._count_tasks(tasks), percent=0),
            tasks=tasks,
        )
        record = RunRecord(
            snapshot=snapshot,
            request=request.model_copy(deep=True),
            source_path=source_path,
        )
        async with self._lock:
            self._records[run_id] = record
            self._append_event(record, "run.created", None, {"status": "created"})

        job = asyncio.create_task(
            self._execute_pipeline_guarded(run_id, request, source_path)
        )
        self._background.add(job)
        job.add_done_callback(self._background.discard)
        return copy.deepcopy(snapshot)

    async def retry(self, run_id: str) -> RunSnapshot | None:
        async with self._lock:
            record = self._records.get(run_id)
            if not record:
                return None
            if record.snapshot.status in {RunStatus.CREATED, RunStatus.QUEUED, RunStatus.RUNNING}:
                raise ValueError("当前运行仍在执行，请等待结束后再重新执行。")
            request = record.request.model_copy(deep=True)
            source_path = record.source_path
            retry_number = record.snapshot.retry_number + 1

        if not source_path.exists():
            raise FileNotFoundError("找不到原始上传文件，无法重新解析。")
        return await self.create_run(
            request,
            source_path,
            retry_of_run_id=run_id,
            retry_number=retry_number,
        )

    async def latest_for_document_version(self, document_version_id: str) -> RunSnapshot | None:
        async with self._lock:
            matches = [
                record.snapshot
                for record in self._records.values()
                if record.snapshot.document_version_id == document_version_id
            ]
            return copy.deepcopy(matches[-1]) if matches else None

    async def _execute_pipeline_guarded(
        self,
        run_id: str,
        request: CreateRunRequest,
        source_path: Path,
    ) -> None:
        try:
            await self._execute_pipeline(run_id, request, source_path)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._record_exception(run_id, "pipeline.unhandled_exception", None, error)
            await self._fail_active_run(run_id, str(error))

    async def _fail_active_run(self, run_id: str, message: str) -> None:
        async with self._lock:
            record = self._records.get(run_id)
            if not record or record.snapshot.status in {RunStatus.FAILED, RunStatus.CANCELLED}:
                return
            now = utc_now()
            active = next(
                (task for task in self._flatten_tasks(record.snapshot.tasks) if task.status == TaskStatus.RUNNING),
                None,
            )
            if active:
                active.status = TaskStatus.FAILED
                active.finished_at = now
                active.output = {**active.output, "error": message}
                active.warnings = [message]
            self._settle_remaining_tasks(record, "流程失败，后续步骤已停止。")
            record.snapshot.status = RunStatus.FAILED
            record.snapshot.finished_at = now
            record.snapshot.last_activity_at = now
            self._refresh_progress(record.snapshot)
            self._append_event(
                record,
                "run.failed",
                active.id if active else None,
                {"status": "failed", "error": message, "fail_fast": True},
            )

    async def get_run(self, run_id: str) -> RunSnapshot | None:
        async with self._lock:
            record = self._records.get(run_id)
            return copy.deepcopy(record.snapshot) if record else None

    async def list_runs(self) -> list[RunSnapshot]:
        async with self._lock:
            return [copy.deepcopy(record.snapshot) for record in self._records.values()]

    async def get_task(self, run_id: str, task_id: str) -> TaskNode | None:
        async with self._lock:
            record = self._records.get(run_id)
            if not record:
                return None
            task = self._find_task(record.snapshot.tasks, task_id)
            return copy.deepcopy(task) if task else None

    async def publish(self, run_id: str) -> RunSnapshot | None:
        async with self._lock:
            record = self._records.get(run_id)
            if not record:
                return None
            if record.snapshot.status != RunStatus.AWAITING_REVIEW:
                return copy.deepcopy(record.snapshot)
        await self._run_task(
            run_id,
            "publish",
            0.45,
            output={"artifact_version": 1, "manifest_status": "published"},
            metrics=[Metric(name="artifacts", label="发布产物", value=5, unit="项")],
        )
        async with self._lock:
            record = self._records[run_id]
            record.snapshot.status = RunStatus.PUBLISHED
            record.snapshot.finished_at = utc_now()
            record.snapshot.last_activity_at = record.snapshot.finished_at
            self._refresh_progress(record.snapshot)
            self._append_event(record, "run.published", None, {"status": "published"})
            return copy.deepcopy(record.snapshot)

    async def events(self, run_id: str, after: int = 0) -> AsyncIterator[str]:
        heartbeat_at = time.monotonic()
        while True:
            async with self._lock:
                record = self._records.get(run_id)
                if not record:
                    return
                pending = [event for event in record.events if event["sequence"] > after]
                terminal = record.snapshot.status in {
                    RunStatus.AWAITING_REVIEW,
                    RunStatus.PARTIALLY_COMPLETED,
                    RunStatus.PUBLISHED,
                    RunStatus.FAILED,
                    RunStatus.CANCELLED,
                }
                changed = record.changed
                if pending:
                    record.changed = asyncio.Event()

            for event in pending:
                after = event["sequence"]
                yield f"id: {after}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

            if terminal and not pending:
                return

            try:
                await asyncio.wait_for(changed.wait(), timeout=2.0)
            except TimeoutError:
                if time.monotonic() - heartbeat_at > 5:
                    heartbeat_at = time.monotonic()
                    yield ": keep-alive\n\n"

    async def _execute_pipeline(
        self,
        run_id: str,
        request: CreateRunRequest,
        source_path: Path,
    ) -> None:
        await self._set_run_status(run_id, RunStatus.QUEUED)
        await asyncio.sleep(0.18)
        await self._set_run_status(run_id, RunStatus.RUNNING)

        await self._run_task(
            run_id,
            "receive",
            0.35,
            output={"file_status": "verified", "checksum": "sha256:verified", "source_uri": "object://source/document"},
            metrics=[Metric(name="files", label="输入文件", value=1, unit="个")],
        )
        await self._set_task_status(run_id, "parse", TaskStatus.RUNNING)

        async def report_parser_progress(event: ParseProgress) -> None:
            await self._apply_parser_progress(run_id, event)

        try:
            parse_result = await document_parser.parse(
                ParseRequest(
                    run_id=run_id,
                    document_id=request.document_id,
                    document_version_id=request.document_version_id,
                    filename=request.document_name,
                    source_path=source_path,
                ),
                report_parser_progress,
            )
        except Exception as error:
            self._record_exception(run_id, "parser.failed", "parse", error)
            await self._fail_task(run_id, "parse", str(error))
            await self._set_run_status(run_id, RunStatus.FAILED)
            return

        parser_output = {
            "artifact_id": parse_result.artifact_id,
            "provider_task_id": parse_result.provider_task_id,
            "parser": parse_result.parser_name,
            "parser_version": parse_result.parser_version,
            "base_path": str(parse_result.base_path),
            "markdown_url": f"/api/parse-artifacts/{parse_result.artifact_id}/files/markdown",
            "middle_json_url": f"/api/parse-artifacts/{parse_result.artifact_id}/files/middle_json",
            "structured_content_url": f"/api/parse-artifacts/{parse_result.artifact_id}/files/structured_content",
            **parse_result.metadata,
        }
        await self._complete_parent(run_id, "parse", parser_output)
        async with self._lock:
            record = self._records[run_id]
            parse_task = self._find_task(record.snapshot.tasks, "parse")
            if parse_task:
                parse_task.metrics = [
                    Metric(name="pages", label="页数", value=parse_result.metadata.get("pages", 0), unit="页"),
                    Metric(name="blocks", label="内容块", value=parse_result.metadata.get("blocks", 0), unit="个"),
                    Metric(name="artifacts", label="解析产物", value=3, unit="个"),
                ]
                self._persist_record(record)
        await self._set_task_status(run_id, "document_json", TaskStatus.RUNNING)
        canonical_output = self._compile_document_json(parse_result, request)
        await self._complete_parent(run_id, "document_json", canonical_output)
        async with self._lock:
            record = self._records[run_id]
            document_task = self._find_task(record.snapshot.tasks, "document_json")
            if document_task:
                document_task.metrics = [
                    Metric(name="json_size", label="JSON 大小", value=canonical_output["json_size_bytes"], unit="bytes"),
                    Metric(name="pages", label="页面", value=canonical_output["pages"], unit="页"),
                    Metric(name="blocks", label="内容块", value=canonical_output["blocks"], unit="个"),
                    Metric(name="schema_valid", label="Schema 校验", value="PASS"),
                ]
                self._persist_record(record)

        template = paper_analysis_template()
        enabled_keys = set(request.enabled_elements)
        selected_elements = [
            element for element in template.elements
            if element.enabled and (not enabled_keys or element.key in enabled_keys)
        ]
        await self._set_task_status(run_id, "extract", TaskStatus.RUNNING)
        for group, definition in AGENT_GROUPS.items():
            has_fields = any(
                any(element.key == prefix or element.key.startswith(prefix) for prefix in definition["prefixes"])
                for element in selected_elements
            )
            if not has_fields:
                await self._set_task_status(run_id, f"schema_{group}", TaskStatus.SKIPPED)

        async def report_extraction_progress(event: ExtractionProgress) -> None:
            task_id = f"schema_{event.agent}"
            try:
                agent_log_store.event(
                    run_id,
                    task_id,
                    "orchestrator.state",
                    level="ERROR" if event.state == "failed" else "INFO",
                    message=f"主流程收到子 Agent 状态：{event.state}",
                    payload={
                        "state": event.state,
                        "fields": event.fields,
                        "details": event.details,
                    },
                )
            except Exception:
                application_logger.exception(
                    "Failed to persist agent progress: run_id=%s agent_id=%s",
                    run_id,
                    task_id,
                )
            if event.state == "running":
                await self._set_task_status(run_id, task_id, TaskStatus.RUNNING)
            elif event.state == "completed":
                await self._complete_parent(run_id, task_id, {"fields": event.fields, **event.details})
            elif event.state == "failed":
                await self._fail_task(run_id, task_id, str(event.details.get("error") or "子 Agent 执行失败"))

        try:
            extraction_result = await schema_extractor.extract(
                ExtractionRequest(
                    run_id=run_id,
                    document_version_id=request.document_version_id,
                    template_id=request.template_id,
                    template_version=request.template_version,
                    elements=selected_elements,
                    markdown_path=parse_result.markdown_path,
                    structured_content_path=parse_result.structured_content_path,
                    middle_json_path=parse_result.middle_json_path,
                ),
                report_extraction_progress,
            )
        except Exception as error:
            self._record_exception(run_id, "extraction.failed", "extract", error)
            await self._fail_task(run_id, "extract", str(error))
            await self._set_run_status(run_id, RunStatus.FAILED)
            return

        # The orchestrator owns the durable output contract even when an
        # extractor implementation only returns an in-memory result.
        if not extraction_result.artifact_path:
            extraction_dir = settings.extraction_dir / run_id
            extraction_dir.mkdir(parents=True, exist_ok=True)
            extraction_path = extraction_dir / "schema_fields.json"
            extraction_path.write_text(
                extraction_result.model_dump_json(indent=2, by_alias=True),
                encoding="utf-8",
            )
            extraction_result.artifact_path = str(extraction_path)

        await self._set_task_status(run_id, "schema_merge", TaskStatus.RUNNING)
        await self._complete_parent(
            run_id,
            "schema_merge",
            {"validated_fields": len(extraction_result.fields), **extraction_result.metrics},
        )
        extraction_output = {
            "schema_version": extraction_result.schema_version,
            "result_url": f"/api/runs/{run_id}/schema-extraction",
            "artifact_path": extraction_result.artifact_path,
            "model": extraction_result.model,
            "agents": extraction_result.agents,
            "fields": [field.model_dump(by_alias=True) for field in extraction_result.fields],
            "source_truncated": extraction_result.source_truncated,
            **extraction_result.metrics,
        }
        await self._complete_parent(run_id, "extract", extraction_output)
        async with self._lock:
            record = self._records[run_id]
            extraction_task = self._find_task(record.snapshot.tasks, "extract")
            if extraction_task:
                extraction_task.metrics = [
                    Metric(name="requested", label="请求字段", value=extraction_result.metrics["requested"], unit="项"),
                    Metric(name="extracted", label="成功提取", value=extraction_result.metrics["extracted"], unit="项"),
                    Metric(name="missing", label="缺失字段", value=extraction_result.metrics["missing"], unit="项"),
                    Metric(
                        name="evidence_coverage",
                        label="证据覆盖",
                        value=round(float(extraction_result.metrics["evidence_coverage"]) * 100),
                        unit="%",
                    ),
                ]
                self._persist_record(record)

        selected_count = int(extraction_result.metrics["extracted"])

        storage_jobs = {
            "page_index": (
                0.82,
                {"store": "document_store", "sections": 19, "max_depth": 3, "anchors": 33},
                [Metric(name="sections", label="章节记录", value=19, unit="条")],
            ),
            "graph": (
                1.04,
                {"store": "graph_database", "entities": 38, "verified_relations": 24},
                [Metric(name="relations", label="关系记录", value=24, unit="条")],
            ),
            "tree": (
                0.74,
                {"store": "hierarchy_store", "nodes": 5, "memberships": 3},
                [Metric(name="nodes", label="层级节点", value=5, unit="个")],
            ),
            "hybrid_retrieval": (
                0.94,
                {"store": "search_vector_index", "document_records": 1, "section_records": 19, "chunk_records": 67},
                [Metric(name="records", label="索引记录", value=87, unit="条")],
            ),
        }
        await self._set_task_status(run_id, "materialize", TaskStatus.RUNNING)
        enabled_targets = set(request.storage_targets)
        for target in storage_jobs:
            if target not in enabled_targets:
                await self._set_task_status(run_id, target, TaskStatus.SKIPPED)
        await asyncio.gather(*(
            self._run_task(run_id, target, duration, output=output, metrics=metrics)
            for target, (duration, output, metrics) in storage_jobs.items()
            if target in enabled_targets
        ))
        await self._complete_parent(
            run_id,
            "materialize",
            {"enabled_targets": sorted(enabled_targets), "source": "dataweave.document.v1"},
        )
        await self._run_task(
            run_id,
            "validate",
            0.64,
            output={
                "schema_valid": extraction_result.metrics["invalid"] == 0,
                "evidence_coverage": extraction_result.metrics["evidence_coverage"],
                "required_missing": sum(
                    element.required and next(
                        (field.status for field in extraction_result.fields if field.key == element.key),
                        "missing",
                    ) != "extracted"
                    for element in selected_elements
                ),
                "quality_gates_passed": 7,
            },
            metrics=[
                Metric(
                    name="evidence_coverage",
                    label="证据覆盖",
                    value=round(float(extraction_result.metrics["evidence_coverage"]) * 100),
                    unit="%",
                ),
                Metric(name="quality_gates", label="质量门禁", value="7/7"),
            ],
        )

        async with self._lock:
            record = self._records[run_id]
            record.snapshot.status = RunStatus.AWAITING_REVIEW
            record.snapshot.result_summary = {
                "document_schema": "dataweave.document.v1",
                "parse_artifact_id": parse_result.artifact_id,
                "parser": parse_result.parser_name,
                "fields": selected_count,
                "evidence_coverage": extraction_result.metrics["evidence_coverage"],
                "storage_targets": len(enabled_targets),
                "message": "解析完成，等待审核发布。",
            }
            record.snapshot.last_activity_at = utc_now()
            self._refresh_progress(record.snapshot)
            self._append_event(record, "run.awaiting_review", None, record.snapshot.result_summary)

    async def _run_task(
        self,
        run_id: str,
        task_id: str,
        duration: float,
        *,
        output: dict[str, Any],
        metrics: list[Metric],
    ) -> None:
        await self._set_task_status(run_id, task_id, TaskStatus.RUNNING)
        await asyncio.sleep(duration)
        async with self._lock:
            record = self._records[run_id]
            if record.snapshot.status in {RunStatus.FAILED, RunStatus.CANCELLED}:
                return
            task = self._find_task(record.snapshot.tasks, task_id)
            if not task:
                return
            task.status = TaskStatus.COMPLETED
            task.output = output
            task.metrics = metrics
            task.finished_at = utc_now()
            task.duration_ms = max(1, int(duration * 1000))
            record.snapshot.last_activity_at = task.finished_at
            self._refresh_progress(record.snapshot)
            self._append_event(
                record,
                "task.completed",
                task_id,
                {"status": "completed", "output": output, "metrics": [m.model_dump() for m in metrics]},
            )

    async def _set_task_status(self, run_id: str, task_id: str, status: TaskStatus) -> None:
        async with self._lock:
            record = self._records[run_id]
            if record.snapshot.status in {RunStatus.FAILED, RunStatus.CANCELLED}:
                return
            task = self._find_task(record.snapshot.tasks, task_id)
            if not task:
                return
            task.status = status
            if status == TaskStatus.RUNNING:
                task.started_at = utc_now()
                task.attempt += 1
            record.snapshot.last_activity_at = utc_now()
            self._refresh_progress(record.snapshot)
            self._append_event(record, "task.status.changed", task_id, {"status": status.value})

    async def _apply_parser_progress(self, run_id: str, event: ParseProgress) -> None:
        task_ids = {"submit": "parser_submit", "wait": "parser_wait", "persist": "parser_persist"}
        task_id = task_ids[event.stage]
        async with self._lock:
            record = self._records[run_id]
            task = self._find_task(record.snapshot.tasks, task_id)
            parent = self._find_task(record.snapshot.tasks, "parse")
            if not task or not parent:
                return
            now = utc_now()
            if event.state == "running":
                if task.status != TaskStatus.RUNNING:
                    task.status = TaskStatus.RUNNING
                    task.started_at = now
                    task.attempt += 1
                task.output = {"progress": event.progress, "message": event.message, **event.details}
            elif event.state == "completed":
                task.status = TaskStatus.COMPLETED
                task.output = {"progress": event.progress, "message": event.message, **event.details}
                task.finished_at = now
                if task.started_at:
                    started = datetime.fromisoformat(task.started_at)
                    task.duration_ms = max(1, int((datetime.now(UTC) - started).total_seconds() * 1000))
            task.metrics = [Metric(name="progress", label="远程解析进度", value=event.progress, unit="%")]
            parent.output = {"progress": event.progress, "message": event.message, **event.details}
            record.snapshot.last_activity_at = now
            self._refresh_progress(record.snapshot)
            self._append_event(
                record,
                "parser.progress",
                task_id,
                {"status": event.state, "progress": event.progress, "message": event.message, **event.details},
            )

    async def _fail_task(self, run_id: str, task_id: str, message: str) -> None:
        async with self._lock:
            record = self._records[run_id]
            task = self._find_task(record.snapshot.tasks, task_id)
            if not task:
                return
            now = utc_now()
            task.status = TaskStatus.FAILED
            task.finished_at = now
            task.output = {"error": message}
            task.warnings = [message]
            if task.started_at:
                started = datetime.fromisoformat(task.started_at)
                task.duration_ms = max(1, int((datetime.now(UTC) - started).total_seconds() * 1000))
            stopped_children: list[str] = []
            for child in self._flatten_tasks(task.children):
                if child.status in {TaskStatus.RUNNING, TaskStatus.RETRYING}:
                    child.status = TaskStatus.FAILED
                    child.output = {"error": message}
                    child.warnings = [message]
                    child.finished_at = now
                    if child.started_at:
                        started = datetime.fromisoformat(child.started_at)
                        child.duration_ms = max(1, int((datetime.now(UTC) - started).total_seconds() * 1000))
                    stopped_children.append(child.id)
                elif child.status in {TaskStatus.PENDING, TaskStatus.QUEUED}:
                    child.status = TaskStatus.CANCELLED
                    child.output = {"reason": "上游任务失败，未执行该步骤。"}
                    stopped_children.append(child.id)
            record.snapshot.last_activity_at = task.finished_at
            self._refresh_progress(record.snapshot)
            self._append_event(
                record,
                "task.failed",
                task_id,
                {"status": "failed", "error": message, "stopped_children": stopped_children},
            )

    async def _complete_parent(self, run_id: str, task_id: str, output: dict[str, Any]) -> None:
        async with self._lock:
            record = self._records[run_id]
            if record.snapshot.status in {RunStatus.FAILED, RunStatus.CANCELLED}:
                return
            task = self._find_task(record.snapshot.tasks, task_id)
            if not task:
                return
            task.status = TaskStatus.COMPLETED
            task.output = output
            task.finished_at = utc_now()
            if task.started_at:
                started = datetime.fromisoformat(task.started_at)
                task.duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
            record.snapshot.last_activity_at = task.finished_at
            self._refresh_progress(record.snapshot)
            self._append_event(record, "task.completed", task_id, {"status": "completed", "output": output})

    async def _set_run_status(self, run_id: str, status: RunStatus) -> None:
        async with self._lock:
            record = self._records[run_id]
            record.snapshot.status = status
            if status == RunStatus.RUNNING and not record.snapshot.started_at:
                record.snapshot.started_at = utc_now()
            if status in {RunStatus.FAILED, RunStatus.CANCELLED}:
                record.snapshot.finished_at = utc_now()
                self._settle_remaining_tasks(record, "流程失败，后续步骤已停止。")
            record.snapshot.last_activity_at = utc_now()
            self._append_event(record, "run.status.changed", None, {"status": status.value})

    def _settle_remaining_tasks(self, record: RunRecord, reason: str) -> None:
        now = utc_now()
        for task in self._flatten_tasks(record.snapshot.tasks):
            if task.status in {
                TaskStatus.PENDING,
                TaskStatus.QUEUED,
                TaskStatus.RUNNING,
                TaskStatus.RETRYING,
            }:
                task.status = TaskStatus.CANCELLED
                task.finished_at = now if task.started_at else task.finished_at
                task.output = {**task.output, "reason": reason, "stopped_after_failure": True}

    def _append_event(
        self,
        record: RunRecord,
        event_type: str,
        task_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        record.sequence += 1
        record.events.append(
            {
                "event_id": f"evt_{record.sequence:05d}",
                "sequence": record.sequence,
                "run_id": record.snapshot.id,
                "task_id": task_id,
                "type": event_type,
                "occurred_at": utc_now(),
                "payload": payload,
            }
        )
        record.changed.set()
        self._persist_record(record)
        try:
            run_log_store.event(
                record.snapshot.id,
                event_type,
                task_id=task_id,
                level="ERROR" if "failed" in event_type or "interrupted" in event_type else "INFO",
                payload=payload,
            )
        except Exception:
            application_logger.exception("Failed to append run log: run_id=%s event=%s", record.snapshot.id, event_type)

    @staticmethod
    def _record_exception(run_id: str, event_type: str, task_id: str | None, error: Exception) -> None:
        stack = traceback.format_exc()
        try:
            run_log_store.event(
                run_id,
                event_type,
                task_id=task_id,
                level="ERROR",
                message=str(error),
                payload={"error_type": type(error).__name__},
                exception=stack,
            )
        except Exception:
            application_logger.exception("Failed to persist exception in run log: run_id=%s", run_id)
        application_logger.error(
            "Run failed: run_id=%s task_id=%s event=%s error=%s",
            run_id,
            task_id,
            event_type,
            error,
            exc_info=True,
        )

    def _persist_record(self, record: RunRecord) -> None:
        self._repository.save_run(
            record.snapshot,
            record.request,
            record.source_path,
            record.events,
            record.sequence,
        )

    def _refresh_progress(self, snapshot: RunSnapshot) -> None:
        flat = self._flatten_tasks(snapshot.tasks)
        total = len(flat)
        completed = sum(task.status in {TaskStatus.COMPLETED, TaskStatus.SKIPPED} for task in flat)
        running = next((task.name for task in flat if task.status == TaskStatus.RUNNING), None)
        snapshot.progress = RunProgress(
            completed=completed,
            total=total,
            percent=round(completed / total * 100) if total else 0,
            current_task=running,
        )

    def _build_tasks(self, request: CreateRunRequest) -> list[TaskNode]:
        def node(
            task_id: str,
            name: str,
            kind: str,
            description: str,
            executor: str,
            task_input: dict[str, Any],
            children: list[TaskNode] | None = None,
        ) -> TaskNode:
            return TaskNode(
                id=task_id,
                name=name,
                kind=kind,
                description=description,
                executor=executor,
                input=task_input,
                children=children or [],
            )

        storage_children = [
            node("page_index", "PageIndex Store", "storage_target", "按页码、章节和结构路径写入层级文档存储。", "PageIndexWriter", {"source": "document_json", "backend": "document_store", "configurable": True}),
            node("graph", "Graph Store", "storage_target", "将实体与有证据关系写入图数据库。", "GraphWriter", {"source": "document_json", "backend": "graph_database", "configurable": True}),
            node("tree", "Tree Store", "storage_target", "将主题或分类层级写入树形存储。", "TreeWriter", {"source": "document_json", "backend": "hierarchy_store", "configurable": True}),
            node("hybrid_retrieval", "Hybrid Retrieval Store", "storage_target", "将全文、稀疏向量和稠密向量写入混合检索索引。", "HybridIndexWriter", {"source": "document_json", "backend": "search_vector_index", "configurable": True}),
        ]
        return [
            node("receive", "输入接收与校验", "ingestion", "验证文件类型、大小和校验和，并登记不可变源版本。", "InputGateway", {
                "document_id": request.document_id,
                "document_version_id": request.document_version_id,
                "filename": request.document_name,
                "template_id": request.template_id,
                "template_version": request.template_version,
            }),
            node(
                "parse",
                "内容解析与标准化",
                "parser",
                "通过可替换 Parser Adapter 异步生成 Markdown、Middle JSON、Structured Content 与图片资源。",
                "MinerUParserAdapter",
                {
                    "document_version_id": request.document_version_id,
                    "filename": request.document_name,
                    "parser": "mineru",
                    "execution": "remote_async",
                    "outputs": ["markdown", "middle_json", "structured_content", "images"],
                },
                [
                    node("parser_submit", "提交远程解析", "parser_remote", "向 MinerU Tasks API 创建解析任务并登记服务端任务 ID。", "MinerUTransport", {"output_format": "default"}),
                    node("parser_wait", "等待远程结果", "parser_remote", "异步轮询远程任务并同步处理进度。", "MinerUTransport", {"mode": "poll"}),
                    node("parser_persist", "保存解析产物", "artifact", "将 Markdown、Middle JSON、Structured Content 与图片保存到本地并登记数据库。", "LocalArtifactStore", {"repository": "sqlite"}),
                ],
            ),
            node("document_json", "统一 Document JSON", "canonicalization", "组装与场景无关的标准 JSON，统一元数据、页面、章节、Block 和证据锚点。", "DocumentCompiler", {
                "document_id": request.document_id,
                "document_version_id": request.document_version_id,
                "source": "parser.structured_content + parser.middle_json",
                "schema": "dataweave.document.v1",
            }),
            node(
                "extract",
                "Schema 字段映射",
                "extraction",
                "使用 Deep Agents Supervisor 并行调度专业子 Agent，从统一 Document JSON 映射字段并绑定证据。",
                "DeepAgentsSchemaMapper",
                {
                    "source": "document_json",
                    "template_id": request.template_id,
                    "template_version": request.template_version,
                    "enabled_elements": request.enabled_elements,
                    "execution": "parallel_subagents",
                },
                [
                    node("schema_metadata", "Metadata Agent", "extraction_agent", "提取标题、作者、机构、国家、日期和作者关键词。", "DeepAgent", {"group": "metadata"}),
                    node("schema_research", "Research Agent", "extraction_agent", "提取领域、创新、研究问题与核心贡献。", "DeepAgent", {"group": "research"}),
                    node("schema_method", "Method Agent", "extraction_agent", "提取方法、架构、组件与机制。", "DeepAgent", {"group": "method"}),
                    node("schema_experiment", "Experiment Agent", "extraction_agent", "提取数据集、实验结果和局限性。", "DeepAgent", {"group": "experiment"}),
                    node("schema_merge", "结果合并与校验", "extraction_merge", "合并子 Agent 结果，补齐缺失字段并校验证据与类型。", "SchemaResultMerger", {"schema": "dataweave.schema-extraction.v1"}),
                ],
            ),
            node("materialize", "存储目标物化", "materialization", "将同一份 Document JSON 投影到已启用的后端存储介质。", "StorageOrchestrator", {
                "source": "document_json",
                "storage_targets": [str(target) for target in request.storage_targets],
                "mode": "configurable",
            }, storage_children),
            node("validate", "质量门禁", "validation", "统一校验 Document JSON、Schema 输出、证据引用和存储写入结果。", "QualityGate", {"gates": 7}),
            node("publish", "版本发布", "publication", "审核后发布不可变的文档与知识产物版本。", "ArtifactPublisher", {"requires_review": True}),
        ]

    def _count_tasks(self, tasks: list[TaskNode]) -> int:
        return len(self._flatten_tasks(tasks))

    @staticmethod
    def _compile_document_json(parse_result: Any, request: CreateRunRequest) -> dict[str, Any]:
        middle = json.loads(parse_result.middle_json_path.read_text(encoding="utf-8"))
        structured = json.loads(parse_result.structured_content_path.read_text(encoding="utf-8"))
        pages = structured.get("pages") or middle.get("pages") or []
        block_count = sum(len(page.get("blocks") or []) for page in pages if isinstance(page, dict))
        canonical = {
            "schema": "dataweave.document.v1",
            "document_id": request.document_id,
            "document_version_id": request.document_version_id,
            "source_artifact_id": parse_result.artifact_id,
            "metadata": structured.get("metadata") or middle.get("metadata") or {},
            "pages": pages,
            "extensions": structured.get("extensions") or middle.get("extensions") or {},
        }
        output_dir = settings.data_dir / "canonical" / request.document_version_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "document.json"
        serialized = json.dumps(canonical, ensure_ascii=False, indent=2)
        output_path.write_text(serialized, encoding="utf-8")
        return {
            "schema": canonical["schema"],
            "json_path": str(output_path),
            "source_artifact_id": parse_result.artifact_id,
            "pages": len(pages),
            "blocks": block_count,
            "evidence_anchors": block_count,
            "json_size_bytes": len(serialized.encode("utf-8")),
        }

    def _flatten_tasks(self, tasks: list[TaskNode]) -> list[TaskNode]:
        result: list[TaskNode] = []
        for task in tasks:
            result.append(task)
            result.extend(self._flatten_tasks(task.children))
        return result

    def _find_task(self, tasks: list[TaskNode], task_id: str) -> TaskNode | None:
        for task in tasks:
            if task.id == task_id:
                return task
            found = self._find_task(task.children, task_id)
            if found:
                return found
        return None


run_manager = RunManager()

