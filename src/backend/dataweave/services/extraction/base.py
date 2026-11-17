from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from dataweave.schemas import TemplateElement


class Evidence(BaseModel):
    quote: str = Field(description="逐字复制的原文证据，禁止改写")
    page_idx: int | None = Field(default=None, description="从 0 开始的 PDF 页索引")
    section: str | None = Field(default=None, description="证据所在章节")


class ExtractedField(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    label: str = ""
    field_type: str = Field(default="string", alias="type")
    status: str = Field(default="missing", description="extracted、missing 或 invalid")
    value: Any = Field(default=None, description="实际抽取值；有明确证据时必须填写，不能只返回 evidence")
    confidence: float = Field(default=0.0, description="0 到 1 的抽取置信度")
    evidence: list[Evidence] = Field(default_factory=list, description="支持 value 的原文证据")


class AgentExtractionResponse(BaseModel):
    fields: list[ExtractedField]


class ExtractionResult(BaseModel):
    schema_version: str = "dataweave.schema-extraction.v1"
    run_id: str
    document_version_id: str
    template: dict[str, Any]
    model: dict[str, Any]
    agents: list[str]
    fields: list[ExtractedField]
    metrics: dict[str, Any]
    source_truncated: bool = False
    artifact_path: str = ""


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    run_id: str
    document_version_id: str
    template_id: str
    template_version: int
    elements: list[TemplateElement]
    markdown_path: Path
    structured_content_path: Path
    middle_json_path: Path


@dataclass(frozen=True, slots=True)
class ExtractionProgress:
    agent: str
    state: str
    fields: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


ProgressCallback = Callable[[ExtractionProgress], Awaitable[None]]


class SchemaExtractor(Protocol):
    async def extract(self, request: ExtractionRequest, progress: ProgressCallback) -> ExtractionResult: ...
