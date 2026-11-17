from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StorageLocation(BaseModel):
    """User-visible ownership marker for every durable DataWeave resource."""

    service: str
    backend: str
    role: str
    authoritative: bool = True
    resource_id: str | None = None


def sqlite_storage() -> list[StorageLocation]:
    return [StorageLocation(service="dataweave", backend="sqlite", role="metadata")]


def local_file_storage() -> list[StorageLocation]:
    return [StorageLocation(service="dataweave", backend="local_filesystem", role="content")]


class TaskStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PUBLISHED = "published"


class StorageTarget(StrEnum):
    PAGE_INDEX = "page_index"
    GRAPH = "graph"
    TREE = "tree"
    HYBRID_RETRIEVAL = "hybrid_retrieval"


class Metric(BaseModel):
    name: str
    label: str
    value: int | float | str
    unit: str | None = None


class TaskNode(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    name: str
    kind: str
    description: str
    executor: str
    status: TaskStatus = TaskStatus.PENDING
    attempt: int = 0
    max_attempts: int = 3
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    metrics: list[Metric] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    children: list["TaskNode"] = Field(default_factory=list)
    storage_locations: list[StorageLocation] = Field(default_factory=sqlite_storage)


class ArtifactTreeEntry(BaseModel):
    name: str
    path: str
    kind: Literal["file", "directory"]
    size: int | None = None
    mime_type: str | None = None
    content_url: str | None = None
    download_url: str | None = None
    children: list["ArtifactTreeEntry"] = Field(default_factory=list)


class ArtifactRoot(BaseModel):
    id: str
    label: str
    description: str
    task_ids: list[str]
    entries: list[ArtifactTreeEntry] = Field(default_factory=list)
    storage_locations: list[StorageLocation] = Field(default_factory=local_file_storage)


class RunArtifactManifest(BaseModel):
    run_id: str
    roots: list[ArtifactRoot] = Field(default_factory=list)


class AgentTraceEvent(BaseModel):
    timestamp: str
    level: str = "INFO"
    event: str
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    exception: str | None = None
    source: str = "agent_log"


class AgentTraceResult(BaseModel):
    fields: list[dict[str, Any]] = Field(default_factory=list)
    field_count: int = 0
    extracted: int = 0
    missing: int = 0
    invalid: int = 0


class AgentTraceResponse(BaseModel):
    run_id: str
    agent_id: str
    agent_name: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    log_path: str
    detailed_trace_available: bool = False
    events: list[AgentTraceEvent] = Field(default_factory=list)
    result: AgentTraceResult = Field(default_factory=AgentTraceResult)
    storage_locations: list[StorageLocation] = Field(default_factory=local_file_storage)


class RunProgress(BaseModel):
    completed: int
    total: int
    percent: int
    current_task: str | None = None


class RunSnapshot(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    document_id: str
    document_version_id: str
    document_name: str
    template_id: str
    template_version: int
    retry_of_run_id: str | None = None
    retry_number: int = 0
    status: RunStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    last_activity_at: str
    progress: RunProgress
    tasks: list[TaskNode]
    result_summary: dict[str, Any] = Field(default_factory=dict)
    storage_locations: list[StorageLocation] = Field(default_factory=sqlite_storage)


class UploadResponse(BaseModel):
    upload_id: str
    document_id: str
    document_version_id: str
    filename: str
    size: int
    sha256: str
    duplicate: bool = False
    status: str = "stored"
    created_at: str
    storage_locations: list[StorageLocation] = Field(default_factory=local_file_storage)


class DocumentSummary(BaseModel):
    document_id: str
    document_version_id: str
    filename: str
    size: int
    uploaded_at: str
    upload_status: str
    run_id: str | None = None
    run_status: str | None = None
    progress: int = 0
    completed_tasks: int = 0
    total_tasks: int = 0
    current_task: str | None = None
    template_version: int | None = None
    storage_locations: list[StorageLocation] = Field(default_factory=local_file_storage)


class TemplateElement(BaseModel):
    key: str
    label: str
    type: str
    required: bool = False
    enabled: bool = True
    section_hints: list[str] = Field(default_factory=list)
    guideline: str = ""


class TemplateResponse(BaseModel):
    id: str
    name: str
    version: int
    description: str
    elements: list[TemplateElement]
    storage_locations: list[StorageLocation] = Field(default_factory=sqlite_storage)


class CreateRunRequest(BaseModel):
    document_id: str
    document_version_id: str
    document_name: str
    template_id: str = "paper_analysis"
    template_version: int = 3
    enabled_elements: list[str] = Field(default_factory=list)
    storage_targets: list[StorageTarget] = Field(
        default_factory=lambda: [
            StorageTarget.PAGE_INDEX,
            StorageTarget.GRAPH,
            StorageTarget.TREE,
            StorageTarget.HYBRID_RETRIEVAL,
        ]
    )


class CreateRunResponse(BaseModel):
    run_id: str
    status: str
    links: dict[str, str]
    storage_locations: list[StorageLocation] = Field(default_factory=sqlite_storage)


class ParseArtifactResponse(BaseModel):
    id: str
    run_id: str
    document_id: str
    document_version_id: str
    parser_name: str
    parser_version: str
    provider_task_id: str | None = None
    status: str
    progress: int
    base_path: str
    files: dict[str, str]
    file_urls: dict[str, str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    storage_locations: list[StorageLocation] = Field(default_factory=local_file_storage)


class RagflowConfigurationUpdate(BaseModel):
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: str | None = Field(default=None, min_length=8, max_length=4096)
    dataset_name: str = Field(min_length=1, max_length=128)
    language: str = Field(default="Chinese", min_length=1, max_length=32)
    parser_id: Literal[
        "general", "qa", "manual", "table", "paper", "book", "laws",
        "presentation", "picture", "one", "audio", "email",
    ] = "paper"

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        from urllib.parse import urlsplit

        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("RAGFlow API 地址必须是有效的 HTTP(S) 地址")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("RAGFlow API 地址不能包含凭据、查询参数或片段")
        if parsed.path not in {"", "/"}:
            raise ValueError("RAGFlow API 地址只能填写服务根地址")
        return normalized

    @field_validator("dataset_name", "language")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空")
        return value

    @field_validator("api_key")
    @classmethod
    def strip_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 8:
            raise ValueError("RAGFlow API Key 长度不足")
        return value


class RagflowConfigurationResponse(BaseModel):
    id: str | None = None
    provider: Literal["ragflow"] = "ragflow"
    base_url: str = "http://localhost:18080"
    api_key_configured: bool = False
    api_key_masked: str | None = None
    dataset_name: str = "DataWeave"
    dataset_id: str | None = None
    language: str = "Chinese"
    parser_id: str = "paper"
    status: Literal["not_configured", "connected", "error"] = "not_configured"
    dataset_operation: Literal["created", "reused"] | None = None
    last_verified_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    storage_locations: list[StorageLocation] = Field(default_factory=sqlite_storage)

