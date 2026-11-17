from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from dataweave.config import settings
from dataweave.schemas import (
    AgentTraceResponse,
    CreateRunRequest,
    CreateRunResponse,
    DocumentSummary,
    ParseArtifactResponse,
    RagflowConfigurationResponse,
    RagflowConfigurationUpdate,
    RunSnapshot,
    TaskNode,
    TemplateResponse,
    UploadResponse,
)
from dataweave.services.run_manager import run_manager
from dataweave.services.parsers import artifact_repository
from dataweave.services.parsers.repository import ParseArtifactRecord
from dataweave.services.state_repository import state_repository
from dataweave.services.ragflow_settings import RagflowApiError, ragflow_settings_service
from dataweave.observability import agent_log_store, application_logger, run_log_store
from dataweave.template_catalog import paper_analysis_template


router = APIRouter(prefix=settings.api_prefix)


def create_run_response(snapshot: RunSnapshot) -> CreateRunResponse:
    return CreateRunResponse(
        run_id=snapshot.id,
        status=snapshot.status,
        links={
            "self": f"{settings.api_prefix}/runs/{snapshot.id}",
            "events": f"{settings.api_prefix}/runs/{snapshot.id}/events",
            "results": f"{settings.api_prefix}/runs/{snapshot.id}/results",
        },
    )


def artifact_response(record: ParseArtifactRecord) -> ParseArtifactResponse:
    files = {
        "markdown": record.markdown_path,
        "middle_json": record.middle_json_path,
        "structured_content": record.structured_content_path,
        "images": record.images_path,
    }
    return ParseArtifactResponse(
        id=record.id,
        run_id=record.run_id,
        document_id=record.document_id,
        document_version_id=record.document_version_id,
        parser_name=record.parser_name,
        parser_version=record.parser_version,
        provider_task_id=record.provider_task_id,
        status=record.status,
        progress=record.progress,
        base_path=record.base_path,
        files=files,
        file_urls={
            kind: f"{settings.api_prefix}/parse-artifacts/{record.id}/files/{kind}"
            for kind in ("markdown", "middle_json", "structured_content")
        },
        metadata=record.metadata,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "dataweave-api"}


@router.get("/templates/default", response_model=TemplateResponse)
async def default_template() -> TemplateResponse:
    return paper_analysis_template()


@router.get("/settings/ragflow", response_model=RagflowConfigurationResponse)
async def get_ragflow_configuration() -> RagflowConfigurationResponse:
    try:
        return ragflow_settings_service.get()
    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail={"code": "credential_unavailable", "message": str(error)},
        ) from error


@router.get("/knowledge-bases", response_model=list[RagflowConfigurationResponse])
async def list_knowledge_base_configurations() -> list[RagflowConfigurationResponse]:
    try:
        return ragflow_settings_service.list()
    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail={"code": "credential_unavailable", "message": str(error)},
        ) from error


@router.get("/knowledge-bases/{configuration_id}", response_model=RagflowConfigurationResponse)
async def get_knowledge_base_configuration(configuration_id: str) -> RagflowConfigurationResponse:
    try:
        configuration = ragflow_settings_service.get_by_id(configuration_id)
    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail={"code": "credential_unavailable", "message": str(error)},
        ) from error
    if not configuration:
        raise HTTPException(
            status_code=404,
            detail={"code": "knowledge_base_not_found", "message": "知识库配置不存在"},
        )
    return configuration


@router.post(
    "/knowledge-bases",
    response_model=RagflowConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base_configuration(
    request: RagflowConfigurationUpdate,
) -> RagflowConfigurationResponse:
    return await _save_knowledge_base_configuration(request)


@router.put("/knowledge-bases/{configuration_id}", response_model=RagflowConfigurationResponse)
async def update_knowledge_base_configuration(
    configuration_id: str,
    request: RagflowConfigurationUpdate,
) -> RagflowConfigurationResponse:
    return await _save_knowledge_base_configuration(request, configuration_id=configuration_id)


async def _save_knowledge_base_configuration(
    request: RagflowConfigurationUpdate,
    *,
    configuration_id: str | None = None,
) -> RagflowConfigurationResponse:
    try:
        return await ragflow_settings_service.configure(
            request,
            configuration_id=configuration_id,
        )
    except RagflowApiError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": "ragflow_configuration_failed", "message": str(error)},
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail={"code": "credential_unavailable", "message": str(error)},
        ) from error


@router.put("/settings/ragflow", response_model=RagflowConfigurationResponse)
async def update_ragflow_configuration(
    request: RagflowConfigurationUpdate,
) -> RagflowConfigurationResponse:
    try:
        current = ragflow_settings_service.get()
        return await ragflow_settings_service.configure(request, configuration_id=current.id)
    except RagflowApiError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": "ragflow_configuration_failed", "message": str(error)},
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail={"code": "credential_unavailable", "message": str(error)},
        ) from error


@router.post("/uploads", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    filename = Path(file.filename or "paper.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail={"code": "unsupported_file", "message": "当前仅支持 PDF 文件。"})

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    upload_id = f"upload_{uuid4().hex[:12]}"
    stored_name = f"{upload_id}.pdf"
    destination = settings.upload_dir / stored_name
    digest = hashlib.sha256()
    size = 0

    try:
        with destination.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "文件不能超过 50 MB。"})
                digest.update(chunk)
                target.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    sha256 = digest.hexdigest()
    existing_document_id = state_repository.find_document_id_by_sha256(sha256)
    duplicate = existing_document_id is not None
    document_id = existing_document_id or f"doc_{uuid4().hex[:12]}"
    response = UploadResponse(
        upload_id=upload_id,
        document_id=document_id,
        document_version_id=f"ver_{uuid4().hex[:12]}",
        filename=filename,
        size=size,
        sha256=sha256,
        duplicate=duplicate,
        created_at=datetime.now(UTC).isoformat(),
    )
    state_repository.create_upload(response, destination)
    application_logger.info(
        "Document stored: upload_id=%s document_version_id=%s filename=%s size=%s",
        response.upload_id,
        response.document_version_id,
        response.filename,
        response.size,
    )
    return response


@router.get("/uploads/{upload_id}", response_model=UploadResponse)
async def get_upload(upload_id: str) -> UploadResponse:
    stored = state_repository.get_upload(upload_id)
    if not stored:
        raise HTTPException(status_code=404, detail={"code": "upload_not_found", "message": "上传记录不存在。"})
    return stored.upload


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents() -> list[DocumentSummary]:
    runs = await run_manager.list_runs()
    runs_by_version = {run.document_version_id: run for run in runs}
    documents = []
    for stored in state_repository.list_uploads():
        upload = stored.upload
        run = runs_by_version.get(upload.document_version_id)
        automatic_total = max((run.progress.total if run else 0) - 1, 0)
        automatic_completed = min(run.progress.completed if run else 0, automatic_total)
        automatic_progress = round(automatic_completed / automatic_total * 100) if automatic_total else 0
        documents.append(
            DocumentSummary(
                document_id=upload.document_id,
                document_version_id=upload.document_version_id,
                filename=upload.filename,
                size=upload.size,
                uploaded_at=upload.created_at,
                upload_status=upload.status,
                run_id=run.id if run else None,
                run_status=run.status if run else None,
                progress=automatic_progress,
                completed_tasks=automatic_completed,
                total_tasks=automatic_total,
                current_task=run.progress.current_task if run else None,
                template_version=run.template_version if run else None,
            )
        )
    return sorted(documents, key=lambda item: item.uploaded_at, reverse=True)


@router.post("/ingestion-runs", response_model=CreateRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_run(request: CreateRunRequest) -> CreateRunResponse:
    source_path = state_repository.source_path_for_version(request.document_version_id)
    if not source_path or not source_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "source_file_not_found", "message": "找不到该文档版本对应的源文件。"},
        )
    snapshot = await run_manager.create_run(request, source_path)
    return create_run_response(snapshot)


@router.post(
    "/documents/{document_version_id}/runs",
    response_model=CreateRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_document(document_version_id: str) -> CreateRunResponse:
    stored = state_repository.get_upload_by_version(document_version_id)
    if not stored:
        raise HTTPException(
            status_code=404,
            detail={"code": "document_not_found", "message": "文档版本不存在。"},
        )
    if not stored.source_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "source_file_not_found", "message": "找不到文档对应的源文件。"},
        )

    latest = await run_manager.latest_for_document_version(document_version_id)
    try:
        if latest:
            snapshot = await run_manager.retry(latest.id)
            if snapshot is None:
                raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
        else:
            snapshot = await run_manager.create_run(
                CreateRunRequest(
                    document_id=stored.upload.document_id,
                    document_version_id=stored.upload.document_version_id,
                    document_name=stored.upload.filename,
                ),
                stored.source_path,
            )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "document_run_active", "message": str(error)},
        ) from error
    return create_run_response(snapshot)


@router.get("/runs/{run_id}", response_model=RunSnapshot)
async def get_run(run_id: str) -> RunSnapshot:
    snapshot = await run_manager.get_run(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
    return snapshot


@router.get("/runs/{run_id}/logs")
async def get_run_log(run_id: str) -> FileResponse:
    snapshot = await run_manager.get_run(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
    try:
        path = run_log_store.path_for(run_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"code": "invalid_run_id", "message": str(error)}) from error
    if not path.exists():
        raise HTTPException(status_code=404, detail={"code": "run_log_not_found", "message": "该运行暂无日志文件。"})
    return FileResponse(path, media_type="application/x-ndjson")


@router.get("/runs/{run_id}/agents/{agent_id}/logs")
async def get_agent_log(run_id: str, agent_id: str) -> FileResponse:
    snapshot = await run_manager.get_run(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
    if agent_id != "schema_supervisor":
        task = await run_manager.get_task(run_id, agent_id)
        if not task or task.executor != "DeepAgent":
            raise HTTPException(
                status_code=404,
                detail={"code": "agent_not_found", "message": "该运行中不存在指定的 Agent。"},
            )
    try:
        path = agent_log_store.path_for(run_id, agent_id)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_agent_log_id", "message": str(error)},
        ) from error
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "agent_log_not_found", "message": "该 Agent 尚未产生执行日志。"},
        )
    return FileResponse(path, media_type="application/x-ndjson")


@router.get(
    "/runs/{run_id}/agents/{agent_id}/trace",
    response_model=AgentTraceResponse,
)
async def get_agent_trace(run_id: str, agent_id: str) -> AgentTraceResponse:
    snapshot = await run_manager.get_run(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})

    task_id = "extract" if agent_id == "schema_supervisor" else agent_id
    task = await run_manager.get_task(run_id, task_id)
    if not task or (agent_id != "schema_supervisor" and task.executor != "DeepAgent"):
        raise HTTPException(
            status_code=404,
            detail={"code": "agent_not_found", "message": "该运行中不存在指定的 Agent。"},
        )
    try:
        path = agent_log_store.path_for(run_id, agent_id)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_agent_log_id", "message": str(error)},
        ) from error

    events: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                entry = {
                    "timestamp": task.started_at or snapshot.created_at,
                    "level": "WARNING",
                    "event": "log.invalid_line",
                    "message": "日志中存在无法解析的行。",
                    "payload": {"line_chars": len(line)},
                }
            entry.pop("run_id", None)
            entry.pop("agent_id", None)
            entry.setdefault("source", "agent_log")
            events.append(entry)

    detailed_trace_available = any(
        event.get("event", "").startswith(("model.", "tool.", "agent.", "supervisor."))
        for event in events
    )
    # Runs completed before detailed callbacks existed still expose an honest
    # lifecycle reconstructed from the durable task snapshot.
    if not detailed_trace_available:
        restored: list[dict] = []
        if task.started_at:
            restored.append({
                "timestamp": task.started_at,
                "level": "INFO",
                "event": "task.started",
                "message": "Agent 已接收字段分组并开始执行。",
                "payload": {"executor": task.executor, "restored": True},
                "source": "task_snapshot",
            })
        if task.finished_at:
            restored.append({
                "timestamp": task.finished_at,
                "level": "ERROR" if task.status == "failed" else "INFO",
                "event": "task.failed" if task.status == "failed" else "task.completed",
                "message": "Agent 执行失败。" if task.status == "failed" else "Agent 已完成字段抽取。",
                "payload": {"duration_ms": task.duration_ms, "restored": True},
                "source": "task_snapshot",
            })
        events = restored + events
    events.sort(key=lambda event: str(event.get("timestamp") or ""))

    parent = await run_manager.get_task(run_id, "extract")
    all_fields = parent.output.get("fields", []) if parent else []
    if not isinstance(all_fields, list):
        all_fields = []
    assigned = task.output.get("fields", []) if agent_id != "schema_supervisor" else []
    assigned_keys = {key for key in assigned if isinstance(key, str)} if isinstance(assigned, list) else set()
    result_fields = [
        field for field in all_fields
        if isinstance(field, dict)
        and (agent_id == "schema_supervisor" or field.get("key") in assigned_keys)
    ]
    result = {
        "fields": result_fields,
        "field_count": len(result_fields),
        "extracted": sum(field.get("status") == "extracted" for field in result_fields),
        "missing": sum(field.get("status") == "missing" for field in result_fields),
        "invalid": sum(field.get("status") == "invalid" for field in result_fields),
    }
    return AgentTraceResponse(
        run_id=run_id,
        agent_id=agent_id,
        agent_name="Schema Extraction Supervisor" if agent_id == "schema_supervisor" else task.name,
        status=str(task.status),
        started_at=task.started_at,
        finished_at=task.finished_at,
        duration_ms=task.duration_ms,
        log_path=str(path),
        detailed_trace_available=detailed_trace_available,
        events=events,
        result=result,
    )


@router.post("/runs/{run_id}/retry", response_model=CreateRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_run(run_id: str) -> CreateRunResponse:
    try:
        snapshot = await run_manager.retry(run_id)
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "run_not_retryable", "message": str(error)},
        ) from error
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "source_file_not_found", "message": str(error)},
        ) from error
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
    return create_run_response(snapshot)


@router.get("/runs/{run_id}/tasks/{task_id}", response_model=TaskNode)
async def get_task(run_id: str, task_id: str) -> TaskNode:
    task = await run_manager.get_task(run_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"code": "task_not_found", "message": "任务节点不存在。"})
    return task


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, last_event_id: str | None = Header(default=None)) -> StreamingResponse:
    snapshot = await run_manager.get_run(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
    try:
        after = int(last_event_id or "0")
    except ValueError:
        after = 0
    return StreamingResponse(
        run_manager.events(run_id, after=after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/publish", response_model=RunSnapshot)
async def publish_run(run_id: str) -> RunSnapshot:
    snapshot = await run_manager.publish(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
    return snapshot


@router.get("/runs/{run_id}/results")
async def get_results(run_id: str) -> dict[str, object]:
    snapshot = await run_manager.get_run(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
    parse_artifacts = artifact_repository.list_for_run(run_id)
    return {
        "run_id": run_id,
        "status": snapshot.status,
        "storage_locations": [location.model_dump() for location in snapshot.storage_locations],
        "summary": snapshot.result_summary,
        "outputs": {
            "document_json": {
                "schema": "dataweave.document.v1",
                "object_ref": f"object://canonical/{snapshot.document_version_id}/document.json",
                "status": "compiled",
                "storage_locations": [
                    {"service": "dataweave", "backend": "local_filesystem", "role": "content", "authoritative": True}
                ],
            },
            "structured_fields": {
                "template_id": snapshot.template_id,
                "template_version": snapshot.template_version,
                "status": "extracted",
                "storage_locations": [
                    {"service": "dataweave", "backend": "local_filesystem", "role": "enhancement", "authoritative": True}
                ],
            },
            "storage_targets": snapshot.result_summary.get("storage_targets", 0),
            "parser_artifacts": [artifact_response(record).model_dump() for record in parse_artifacts],
        },
    }


@router.get("/runs/{run_id}/schema-extraction")
async def get_schema_extraction(run_id: str) -> FileResponse:
    snapshot = await run_manager.get_run(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
    extraction_task = next((task for task in snapshot.tasks if task.id == "extract"), None)
    artifact_path = extraction_task.output.get("artifact_path") if extraction_task else None
    if not isinstance(artifact_path, str) or not artifact_path:
        raise HTTPException(
            status_code=404,
            detail={"code": "schema_extraction_not_found", "message": "Schema 字段映射结果尚未生成。"},
        )
    resolved = Path(artifact_path).resolve()
    extraction_root = settings.extraction_dir.resolve()
    if extraction_root not in resolved.parents or not resolved.is_file():
        raise HTTPException(
            status_code=404,
            detail={"code": "schema_extraction_file_not_found", "message": "Schema 字段映射结果文件不存在。"},
        )
    return FileResponse(resolved, media_type="application/json", filename="schema_fields.json")


@router.get("/runs/{run_id}/parse-artifacts", response_model=list[ParseArtifactResponse])
async def list_parse_artifacts(run_id: str) -> list[ParseArtifactResponse]:
    snapshot = await run_manager.get_run(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "运行不存在。"})
    return [artifact_response(record) for record in artifact_repository.list_for_run(run_id)]


@router.get("/parse-artifacts/{artifact_id}", response_model=ParseArtifactResponse)
async def get_parse_artifact(artifact_id: str) -> ParseArtifactResponse:
    record = artifact_repository.get(artifact_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "artifact_not_found", "message": "解析产物不存在。"})
    return artifact_response(record)


@router.get("/parse-artifacts/{artifact_id}/files/{kind}")
async def read_parse_artifact_file(artifact_id: str, kind: str) -> FileResponse:
    record = artifact_repository.get(artifact_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "artifact_not_found", "message": "解析产物不存在。"})
    paths = {
        "markdown": (Path(record.markdown_path), "text/markdown; charset=utf-8"),
        "middle_json": (Path(record.middle_json_path), "application/json"),
        "structured_content": (Path(record.structured_content_path), "application/json"),
    }
    selected = paths.get(kind)
    if not selected:
        raise HTTPException(status_code=400, detail={"code": "unsupported_artifact_kind", "message": "不支持的解析产物类型。"})
    path, media_type = selected
    base_path = Path(record.base_path).resolve()
    resolved = path.resolve()
    if base_path not in resolved.parents or not resolved.is_file():
        raise HTTPException(status_code=404, detail={"code": "artifact_file_not_found", "message": "解析产物文件不存在。"})
    return FileResponse(resolved, media_type=media_type, filename=resolved.name)

