from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ParseRequest:
    run_id: str
    document_id: str
    document_version_id: str
    filename: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class ParseProgress:
    stage: str
    state: str
    progress: int
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParseResult:
    artifact_id: str
    provider_task_id: str
    parser_name: str
    parser_version: str
    base_path: Path
    markdown_path: Path
    middle_json_path: Path
    structured_content_path: Path
    images_path: Path
    metadata: dict[str, Any]


ProgressCallback = Callable[[ParseProgress], Awaitable[None]]


class DocumentParser(Protocol):
    name: str

    async def parse(self, request: ParseRequest, progress: ProgressCallback) -> ParseResult: ...
