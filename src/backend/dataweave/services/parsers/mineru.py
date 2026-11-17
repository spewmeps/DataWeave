from __future__ import annotations

import asyncio
import json
import time
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import httpx

from dataweave.services.parsers.base import ParseProgress, ParseRequest, ParseResult, ProgressCallback
from dataweave.services.parsers.repository import ParseArtifactRecord, ParseArtifactRepository, utc_now


@dataclass(frozen=True, slots=True)
class MinerUTaskReceipt:
    task_id: str
    file_id: str


@dataclass(frozen=True, slots=True)
class MinerUOutput:
    markdown: str
    middle_json: dict[str, Any]
    structured_content: dict[str, Any]
    images: dict[str, bytes]
    metadata: dict[str, Any]


class MinerUTransport(Protocol):
    async def submit(self, source_path: Path, filename: str) -> MinerUTaskReceipt: ...

    async def wait_for_result(
        self,
        receipt: MinerUTaskReceipt,
        on_progress: Callable[[int, str], Awaitable[None]],
    ) -> MinerUOutput: ...


class MockMinerUTransport:
    """Simulates a remote MinerU task without coupling the parser to the mock."""

    def __init__(self, tier: str) -> None:
        self.tier = tier
        self._sources: dict[str, tuple[Path, str]] = {}

    async def submit(self, source_path: Path, filename: str) -> MinerUTaskReceipt:
        await asyncio.sleep(0.18)
        task_id = f"mineru_task_{uuid4().hex[:12]}"
        file_id = f"mineru_file_{uuid4().hex[:10]}"
        self._sources[task_id] = (source_path, filename)
        return MinerUTaskReceipt(task_id=task_id, file_id=file_id)

    async def wait_for_result(self, receipt: MinerUTaskReceipt, on_progress: Callable[[int, str], Awaitable[None]]) -> MinerUOutput:
        source_path, filename = self._sources[receipt.task_id]
        for percent, message in ((28, "远程服务正在分析版面"), (57, "正在识别正文、公式与表格"), (86, "正在生成结构化结果")):
            await asyncio.sleep(0.22)
            await on_progress(percent, message)

        size = source_path.stat().st_size
        title = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Untitled Document"
        markdown = (
            f"# {title}\n\n"
            "## 解析说明\n\n"
            "本文档由 DataWeave 的 MinerU Mock Transport 解析。接入真实远程服务后，"
            "这里将保存 MinerU 返回的完整标题、章节、公式、表格与图片引用。\n\n"
            "## Document Metadata\n\n"
            f"- Source file: `{filename}`\n"
            f"- Source bytes: `{size}`\n"
            f"- Parser tier: `{self.tier}`\n"
        )
        blocks = [
            {"type": "text", "index": 0, "content": [{"type": "text", "content": title}]},
            {"type": "text", "index": 1, "content": [{"type": "text", "content": "MinerU Mock parsing result for DataWeave."}]},
        ]
        metadata = {
            "file_suffix": "pdf",
            "producer": {"name": "mineru", "version": "4.1-mock"},
        }
        extensions = {"mineru": {"tier": self.tier, "parse_mode": "mock"}}
        middle_json = {
            "metadata": metadata,
            "extensions": extensions,
            "pages": [{"page_idx": 0, "blocks": blocks}],
            "is_full_document": True,
            "schema": "docvortex.middle",
            "schema_version": "2.0",
        }
        structured_content = {
            "pages": [{"page_idx": 0, "blocks": [
                {"type": "text", "content": title},
                {"type": "text", "content": "MinerU Mock parsing result for DataWeave."},
            ]}],
            "metadata": metadata,
            "extensions": extensions,
            "is_full_document": True,
        }
        return MinerUOutput(
            markdown=markdown,
            middle_json=middle_json,
            structured_content=structured_content,
            images={},
            metadata={"pages": 1, "blocks": 2, "tables": 0, "figures": 0, "tier": self.tier, "parse_mode": "mock"},
        )


class RemoteMinerUTransport:
    """MinerU Cloud v4 batch upload, polling and ZIP normalization transport."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model_version: str,
        timeout_seconds: float,
        poll_interval_seconds: float,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model_version = model_version
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._filenames: dict[str, str] = {}

    @property
    def headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("MINERU_API_KEY 未配置。")
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    async def submit(self, source_path: Path, filename: str) -> MinerUTaskReceipt:
        data_id = f"dw_{uuid4().hex[:16]}"
        request_body = {
            "files": [{"name": filename, "data_id": data_id}],
            "model_version": self.model_version,
            "enable_formula": True,
            "enable_table": True,
        }
        timeout = httpx.Timeout(self.timeout_seconds, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(
                f"{self.api_url}/api/v4/file-urls/batch",
                headers={**self.headers, "Content-Type": "application/json"},
                json=request_body,
            )
            if response.status_code == 401:
                try:
                    error_body = response.json()
                except ValueError:
                    error_body = {}
                error_code = error_body.get("msgCode") or "HTTP 401"
                error_message = error_body.get("msg") or "user authenticate failed"
                raise RuntimeError(f"MinerU 鉴权失败（{error_code}）：{error_message}")
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 0:
                raise RuntimeError(f"MinerU 申请上传地址失败：{payload.get('msg', 'unknown error')}")
            data = payload.get("data") or {}
            batch_id = str(data.get("batch_id") or "")
            upload_urls = data.get("file_urls") or []
            if not batch_id or not upload_urls:
                raise RuntimeError("MinerU 返回缺少 batch_id 或 file_urls。")
            with source_path.open("rb") as source:
                upload = await client.put(str(upload_urls[0]), content=source.read(), headers={"Accept": "*/*"})
            upload.raise_for_status()
        self._filenames[batch_id] = filename
        return MinerUTaskReceipt(task_id=batch_id, file_id=data_id)

    async def wait_for_result(self, receipt: MinerUTaskReceipt, on_progress: Callable[[int, str], Awaitable[None]]) -> MinerUOutput:
        started = time.monotonic()
        timeout = httpx.Timeout(60.0, connect=30.0)
        filename = self._filenames.get(receipt.task_id, "")
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            while time.monotonic() - started < self.timeout_seconds:
                response = await client.get(
                    f"{self.api_url}/api/v4/extract-results/batch/{receipt.task_id}",
                    headers=self.headers,
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("code") != 0:
                    raise RuntimeError(f"MinerU 查询任务失败：{payload.get('msg', 'unknown error')}")
                results = (payload.get("data") or {}).get("extract_result") or []
                result = next(
                    (item for item in results if item.get("data_id") == receipt.file_id),
                    next((item for item in results if item.get("file_name") == filename), results[0] if results else None),
                )
                if not result:
                    await on_progress(18, "远程任务已创建，等待 MinerU 接收文件")
                    await asyncio.sleep(self.poll_interval_seconds)
                    continue
                state = str(result.get("state") or "pending")
                if state == "done":
                    zip_url = result.get("full_zip_url")
                    if not zip_url:
                        raise RuntimeError("MinerU 任务已完成，但未返回 full_zip_url。")
                    await on_progress(86, "MinerU 解析完成，正在下载结果包")
                    archive = await client.get(str(zip_url), headers={"Accept": "application/zip"})
                    archive.raise_for_status()
                    return self._read_result_zip(archive.content, filename)
                if state == "failed":
                    raise RuntimeError(f"MinerU 解析失败：{result.get('err_msg') or 'unknown error'}")
                extract_progress = result.get("extract_progress") or {}
                extracted = int(extract_progress.get("extracted_pages") or 0)
                total = int(extract_progress.get("total_pages") or 0)
                percent = 20 + round(extracted / total * 60) if total else 24
                labels = {
                    "waiting-file": "等待 MinerU 接收上传文件",
                    "pending": "MinerU 任务排队中",
                    "running": "MinerU 正在解析文档",
                    "converting": "MinerU 正在生成输出格式",
                }
                await on_progress(min(percent, 84), labels.get(state, f"MinerU 状态：{state}"))
                await asyncio.sleep(self.poll_interval_seconds)
        raise TimeoutError(f"MinerU 任务轮询超时，batch_id={receipt.task_id}")

    def _read_result_zip(self, content: bytes, filename: str) -> MinerUOutput:
        markdown = ""
        middle_json: dict[str, Any] | None = None
        structured_content: dict[str, Any] | None = None
        content_list: list[dict[str, Any]] | None = None
        content_list_v2: list[Any] | None = None
        images: dict[str, bytes] = {}
        with zipfile.ZipFile(BytesIO(content)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                name = member.filename.replace("\\", "/")
                raw = archive.read(member)
                lower_name = name.lower()
                if lower_name.endswith(".md") and (not markdown or lower_name.endswith("full.md") or lower_name.endswith("markdown.md")):
                    markdown = raw.decode("utf-8", errors="replace")
                elif lower_name.endswith(".json"):
                    try:
                        parsed = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    if isinstance(parsed, dict) and (
                        parsed.get("schema") == "docvortex.middle" or "middle" in Path(lower_name).stem
                    ):
                        middle_json = parsed
                    elif isinstance(parsed, dict) and "structured_content" in Path(lower_name).stem:
                        structured_content = parsed
                    elif isinstance(parsed, list) and "content_list" in Path(lower_name).stem:
                        if "content_list_v2" in Path(lower_name).stem:
                            content_list_v2 = parsed
                        elif all(isinstance(item, dict) for item in parsed):
                            content_list = parsed
                elif "/images/" in f"/{lower_name}" or lower_name.startswith("images/"):
                    images[Path(name).name] = raw

        if content_list is None and content_list_v2 is not None:
            content_list = self._flatten_content_list_v2(content_list_v2)
        if not markdown:
            raise RuntimeError("MinerU ZIP 中未找到 Markdown 文件。")
        if middle_json is None:
            middle_json = self._middle_from_content_list(content_list or [], filename)
        if structured_content is None:
            structured_content = self._structured_from_content_list(content_list or [], filename)
        pages = middle_json.get("pages") or middle_json.get("pdf_info") or []
        block_count = sum(len(page.get("blocks") or page.get("para_blocks") or []) for page in pages if isinstance(page, dict))
        metadata = {
            "pages": len(pages),
            "blocks": block_count or len(content_list or []),
            "tables": sum(1 for item in content_list or [] if item.get("type") == "table"),
            "figures": sum(1 for item in content_list or [] if item.get("type") in {"image", "figure"}),
            "model_version": self.model_version,
            "parse_mode": "mineru_cloud_v4",
        }
        return MinerUOutput(markdown, middle_json, structured_content, images, metadata)

    def _middle_from_content_list(self, items: list[dict[str, Any]], filename: str) -> dict[str, Any]:
        pages = self._group_content_list(items)
        return {
            "metadata": {"file_suffix": Path(filename).suffix.lstrip("."), "producer": {"name": "mineru-cloud", "version": "v4"}},
            "extensions": {"mineru": {"model_version": self.model_version, "parse_mode": "cloud"}},
            "pages": pages,
            "is_full_document": True,
            "schema": "dataweave.normalized-middle",
            "schema_version": "1.0",
        }

    def _structured_from_content_list(self, items: list[dict[str, Any]], filename: str) -> dict[str, Any]:
        pages = self._group_content_list(items)
        return {
            "pages": pages,
            "metadata": {"file_suffix": Path(filename).suffix.lstrip("."), "producer": {"name": "mineru-cloud", "version": "v4"}},
            "extensions": {"mineru": {"model_version": self.model_version, "parse_mode": "cloud"}},
            "is_full_document": True,
        }

    @staticmethod
    def _group_content_list(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[int, list[dict[str, Any]]] = {}
        for item in items:
            page_idx = int(item.get("page_idx") or item.get("page_index") or 0)
            content = item.get("text") or item.get("content") or item.get("table_body") or ""
            grouped.setdefault(page_idx, []).append({"type": item.get("type", "text"), "content": content})
        return [{"page_idx": page_idx, "blocks": blocks} for page_idx, blocks in sorted(grouped.items())]

    @staticmethod
    def _flatten_content_list_v2(pages: list[Any]) -> list[dict[str, Any]]:
        """Normalize MinerU's page-nested content_list_v2 as a safe fallback."""

        flattened: list[dict[str, Any]] = []
        for page_idx, page in enumerate(pages):
            if not isinstance(page, list):
                continue
            for item in page:
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                normalized.setdefault("page_idx", page_idx)
                flattened.append(normalized)
        return flattened


class MinerUParser:
    name = "mineru"

    def __init__(self, transport: MinerUTransport, repository: ParseArtifactRepository, artifact_root: Path) -> None:
        self.transport = transport
        self.repository = repository
        self.artifact_root = artifact_root

    async def parse(self, request: ParseRequest, progress: ProgressCallback) -> ParseResult:
        artifact_id = f"artifact_{uuid4().hex[:12]}"
        base_path = self.artifact_root / request.document_version_id / artifact_id
        markdown_path = base_path / "markdown.md"
        middle_json_path = base_path / "middle_json.json"
        structured_content_path = base_path / "structured_content.json"
        images_path = base_path / "images"
        now = utc_now()
        record = ParseArtifactRecord(
            id=artifact_id,
            run_id=request.run_id,
            document_id=request.document_id,
            document_version_id=request.document_version_id,
            parser_name=self.name,
            parser_version="pending",
            provider_task_id=None,
            status="created",
            progress=0,
            base_path=str(base_path),
            markdown_path=str(markdown_path),
            middle_json_path=str(middle_json_path),
            structured_content_path=str(structured_content_path),
            images_path=str(images_path),
            metadata={},
            created_at=now,
            updated_at=now,
        )
        self.repository.create(record)

        try:
            await progress(ParseProgress("submit", "running", 5, "正在提交 MinerU 远程解析任务"))
            receipt = await self.transport.submit(request.source_path, request.filename)
            self.repository.update(
                artifact_id,
                provider_task_id=receipt.task_id,
                status="running",
                progress=15,
            )
            await progress(ParseProgress(
                "submit", "completed", 15, "远程任务已创建",
                {"provider_task_id": receipt.task_id, "file_id": receipt.file_id, "parser": self.name},
            ))

            await progress(ParseProgress("wait", "running", 16, "等待 MinerU 返回解析结果", {"provider_task_id": receipt.task_id}))

            async def remote_progress(percent: int, message: str) -> None:
                mapped = min(85, max(16, percent))
                self.repository.update(artifact_id, progress=mapped)
                await progress(ParseProgress("wait", "running", mapped, message, {"remote_progress": percent}))

            output = await self.transport.wait_for_result(receipt, remote_progress)
            await progress(ParseProgress("wait", "completed", 88, "MinerU 解析完成，开始保存结果", output.metadata))

            await progress(ParseProgress("persist", "running", 90, "正在保存 Markdown、JSON 与图片资源"))
            images_path.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(output.markdown, encoding="utf-8")
            middle_json_path.write_text(json.dumps(output.middle_json, ensure_ascii=False, indent=2), encoding="utf-8")
            structured_content_path.write_text(json.dumps(output.structured_content, ensure_ascii=False, indent=2), encoding="utf-8")
            for relative_name, content in output.images.items():
                target = images_path / Path(relative_name).name
                target.write_bytes(content)

            parser_version = str(output.middle_json.get("metadata", {}).get("producer", {}).get("version", "unknown"))
            self.repository.update(
                artifact_id,
                parser_version=parser_version,
                status="completed",
                progress=100,
                metadata=output.metadata,
            )
            file_urls = {
                "markdown_url": f"/api/parse-artifacts/{artifact_id}/files/markdown",
                "middle_json_url": f"/api/parse-artifacts/{artifact_id}/files/middle_json",
                "structured_content_url": f"/api/parse-artifacts/{artifact_id}/files/structured_content",
            }
            await progress(ParseProgress(
                "persist", "completed", 100, "解析产物已保存并登记",
                {"artifact_id": artifact_id, "base_path": str(base_path), **file_urls},
            ))
            return ParseResult(
                artifact_id=artifact_id,
                provider_task_id=receipt.task_id,
                parser_name=self.name,
                parser_version=parser_version,
                base_path=base_path,
                markdown_path=markdown_path,
                middle_json_path=middle_json_path,
                structured_content_path=structured_content_path,
                images_path=images_path,
                metadata=output.metadata,
            )
        except Exception as error:
            self.repository.update(artifact_id, status="failed", metadata={"error": str(error)})
            raise
