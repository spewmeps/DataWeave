from __future__ import annotations

import json
import re
import time
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

from deepagents import CompiledSubAgent, create_deep_agent
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from dataweave.observability import agent_log_store
from dataweave.services.extraction.base import (
    AgentExtractionResponse,
    Evidence,
    ExtractedField,
    ExtractionProgress,
    ExtractionRequest,
    ExtractionResult,
    ProgressCallback,
)


class AgentExecutionCallback(AsyncCallbackHandler):
    """Write privacy-safe model/tool traces for one extraction Agent.

    The parsed paper and prompt bodies are deliberately not copied into logs.
    Operators get call counts, sizes, latency, token usage and exceptions while
    the actual source/result remains in the normal run artifacts.
    """

    def __init__(self, dataweave_run_id: str, agent_id: str, agent_name: str) -> None:
        self.dataweave_run_id = dataweave_run_id
        self.agent_id = agent_id
        self.agent_name = agent_name
        self._started: dict[str, float] = {}

    def _event(
        self,
        event_type: str,
        framework_run_id: UUID,
        *,
        level: str = "INFO",
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        exception: str | None = None,
    ) -> None:
        agent_log_store.event(
            self.dataweave_run_id,
            self.agent_id,
            event_type,
            level=level,
            message=message,
            payload={
                "agent_name": self.agent_name,
                "framework_run_id": str(framework_run_id),
                **(payload or {}),
            },
            exception=exception,
        )

    def _duration_ms(self, framework_run_id: UUID) -> int | None:
        started = self._started.pop(str(framework_run_id), None)
        return round((time.monotonic() - started) * 1000) if started is not None else None

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._started[str(run_id)] = time.monotonic()
        message_count = sum(len(batch) for batch in messages)
        input_chars = sum(
            len(str(getattr(message, "content", "")))
            for batch in messages
            for message in batch
        )
        self._event(
            "model.started",
            run_id,
            payload={
                "parent_framework_run_id": str(parent_run_id) if parent_run_id else None,
                "model": serialized.get("name") or serialized.get("id") or "chat-model",
                "message_count": message_count,
                "input_chars": input_chars,
                "content_logged": False,
            },
        )

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        usage: dict[str, Any] = {}
        if isinstance(response.llm_output, dict):
            raw_usage = response.llm_output.get("token_usage") or response.llm_output.get("usage")
            if isinstance(raw_usage, dict):
                usage = raw_usage
        output_chars = 0
        for batch in response.generations:
            for generation in batch:
                text = getattr(generation, "text", "")
                message = getattr(generation, "message", None)
                output_chars += len(str(getattr(message, "content", text) or ""))
                if not usage and message is not None:
                    raw_usage = getattr(message, "usage_metadata", None)
                    if isinstance(raw_usage, dict):
                        usage = raw_usage
        self._event(
            "model.completed",
            run_id,
            payload={
                "parent_framework_run_id": str(parent_run_id) if parent_run_id else None,
                "duration_ms": self._duration_ms(run_id),
                "output_chars": output_chars,
                "token_usage": usage,
                "content_logged": False,
            },
        )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._event(
            "model.failed",
            run_id,
            level="ERROR",
            message=str(error),
            payload={
                "parent_framework_run_id": str(parent_run_id) if parent_run_id else None,
                "duration_ms": self._duration_ms(run_id),
                "error_type": type(error).__name__,
            },
            exception="".join(traceback.format_exception(type(error), error, error.__traceback__)),
        )

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._started[str(run_id)] = time.monotonic()
        self._event(
            "tool.started",
            run_id,
            payload={
                "parent_framework_run_id": str(parent_run_id) if parent_run_id else None,
                "tool": serialized.get("name") or "unknown-tool",
                "input_chars": len(input_str),
                "input_keys": sorted(inputs) if isinstance(inputs, dict) else [],
                "content_logged": False,
            },
        )

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._event(
            "tool.completed",
            run_id,
            payload={
                "parent_framework_run_id": str(parent_run_id) if parent_run_id else None,
                "duration_ms": self._duration_ms(run_id),
                "output_type": type(output).__name__,
                "output_chars": len(str(output)),
                "content_logged": False,
            },
        )

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._event(
            "tool.failed",
            run_id,
            level="ERROR",
            message=str(error),
            payload={
                "parent_framework_run_id": str(parent_run_id) if parent_run_id else None,
                "duration_ms": self._duration_ms(run_id),
                "error_type": type(error).__name__,
            },
            exception="".join(traceback.format_exception(type(error), error, error.__traceback__)),
        )


AGENT_GROUPS: dict[str, dict[str, Any]] = {
    "metadata": {
        "name": "metadata-agent",
        "description": "提取论文标题、作者、作者机构与国家、发表日期和作者关键词。",
        "prefixes": ("paper.title", "paper.authors", "paper.affiliations", "paper.publication_date", "paper.author_keywords"),
    },
    "research": {
        "name": "research-agent",
        "description": "提取研究领域、创新关键词、研究问题和核心贡献。",
        "prefixes": ("research.",),
    },
    "method": {
        "name": "method-agent",
        "description": "提取方法、架构、组件、机制与处理流程。",
        "prefixes": ("method.",),
    },
    "experiment": {
        "name": "experiment-agent",
        "description": "提取实验数据集、实验结果和作者明确披露的局限性。",
        "prefixes": ("experiments.", "paper.limitations"),
    },
}


SUPERVISOR_PROMPT = """你是 DataWeave 的 Schema Extraction Supervisor。

你必须把任务委派给已定义的专业子 Agent，禁止自己阅读原文并直接抽取字段。

执行规则：
1. 根据用户给出的 active_agents，为每个 Agent 发起一次 task 调用。
2. 必须在同一个模型回合中同时发起全部 task 调用，使它们并行执行；禁止逐个等待后再调用下一个。
3. 子 Agent 会通过自己的工具读取文档和已分配字段，不要在 task 描述中复制全文。
4. 收到全部结果后合并字段。每个 requested_key 必须恰好出现一次。
5. 未找到的字段返回 status=missing、value=null 或 []，绝不推测。
6. 保留子 Agent 返回的原文证据、页码和置信度。
7. 最终只通过结构化响应返回 fields。
"""


SUBAGENT_PROMPT = """你是 DataWeave 的专业论文信息抽取 Agent。

必须先调用 read_assigned_fields 获取字段定义，再调用 read_document_source 获取带页码的论文内容。只抽取分配给你的字段。

输出要求：
- 最终返回一个 JSON 对象，格式为 {"fields": [...]}；不要输出 Markdown 代码块。
- 每个分配字段恰好返回一次，并保留 key、label、type。
- status 仅允许 extracted、missing、invalid。
- 没有明确依据时返回 missing，不允许利用常识补全。
- string 返回字符串；list 返回数组；object 返回对象。
- confidence 为 0 到 1。
- evidence.quote 必须逐字来自原文；page_idx 使用 [PAGE n] 中的 n；section 可为空。
- 多作者、多机构、多结果必须完整保留为列表。
"""


def create_source_tool(source_text: str):
    @tool("read_document_source")
    def read_document_source() -> str:
        """读取当前论文的完整解析文本，包含 [PAGE n] 页码标记。"""
        return source_text

    return read_document_source


def create_fields_tool(payload: list[dict[str, Any]]):
    @tool("read_assigned_fields")
    def read_assigned_fields() -> str:
        """读取分配给当前子 Agent 的 Schema 字段定义。"""
        return json.dumps(payload, ensure_ascii=False)

    return read_assigned_fields


class DeepAgentsSchemaExtractor:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_name: str,
        artifact_root: Path,
        max_source_chars: int,
        enable_thinking: bool,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.artifact_root = artifact_root
        self.max_source_chars = max_source_chars
        self.enable_thinking = enable_thinking
        self.timeout_seconds = timeout_seconds

    async def extract(self, request: ExtractionRequest, progress: ProgressCallback) -> ExtractionResult:
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置，无法执行 Schema 字段映射。")

        source, truncated = self._build_source(request)
        grouped = self._group_elements(request)
        active_groups = [group for group in AGENT_GROUPS if grouped[group]]
        if not active_groups:
            raise RuntimeError("当前模板没有启用任何可抽取字段。")

        model = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model_name,
            temperature=0,
            timeout=self.timeout_seconds,
            max_retries=2,
            extra_body={"enable_thinking": self.enable_thinking},
        )
        subagents: list[CompiledSubAgent] = []
        for group in active_groups:
            element_payload = [item.model_dump() for item in grouped[group]]
            definition = AGENT_GROUPS[group]
            agent_id = f"schema_{group}"
            worker = create_agent(
                model=model,
                tools=[create_source_tool(source), create_fields_tool(element_payload)],
                system_prompt=SUBAGENT_PROMPT,
                response_format=ToolStrategy(AgentExtractionResponse),
                name=definition["name"],
            )

            async def run_worker(
                state: dict[str, Any],
                current_worker=worker,
                current_agent_id=agent_id,
                current_agent_name=definition["name"],
                current_fields=tuple(item.key for item in grouped[group]),
            ) -> dict[str, Any]:
                started = time.monotonic()
                callback = AgentExecutionCallback(
                    request.run_id,
                    current_agent_id,
                    current_agent_name,
                )
                agent_log_store.event(
                    request.run_id,
                    current_agent_id,
                    "agent.started",
                    message="专业字段抽取 Agent 开始执行。",
                    payload={
                        "agent_name": current_agent_name,
                        "assigned_fields": list(current_fields),
                        "field_count": len(current_fields),
                        "framework": "deepagents",
                    },
                )
                try:
                    worker_result = await current_worker.ainvoke(
                        state,
                        config={"callbacks": [callback]},
                    )
                    structured = worker_result.get("structured_response")
                    if structured is None:
                        structured = self._parse_message_response(worker_result)
                    elif isinstance(structured, dict):
                        structured = AgentExtractionResponse.model_validate(structured)
                    agent_log_store.event(
                        request.run_id,
                        current_agent_id,
                        "agent.completed",
                        message="专业字段抽取 Agent 执行完成。",
                        payload={
                            "agent_name": current_agent_name,
                            "duration_ms": round((time.monotonic() - started) * 1000),
                            "returned_fields": [field.key for field in structured.fields],
                            "extracted": sum(field.status == "extracted" for field in structured.fields),
                            "missing": sum(field.status == "missing" for field in structured.fields),
                        },
                    )
                    return {"messages": [AIMessage(content=structured.model_dump_json(by_alias=True))]}
                except Exception as error:
                    agent_log_store.event(
                        request.run_id,
                        current_agent_id,
                        "agent.failed",
                        level="ERROR",
                        message=str(error),
                        payload={
                            "agent_name": current_agent_name,
                            "duration_ms": round((time.monotonic() - started) * 1000),
                            "error_type": type(error).__name__,
                        },
                        exception="".join(traceback.format_exception(type(error), error, error.__traceback__)),
                    )
                    raise

            subagents.append(CompiledSubAgent(
                name=definition["name"],
                description=definition["description"],
                runnable=RunnableLambda(run_worker),
            ))

        supervisor = create_deep_agent(
            model=model,
            name="schema-extraction-supervisor",
            system_prompt=SUPERVISOR_PROMPT,
            subagents=subagents,
            response_format=ToolStrategy(AgentExtractionResponse),
        )

        for group in active_groups:
            await progress(ExtractionProgress(
                agent=group,
                state="running",
                fields=[item.key for item in grouped[group]],
                details={"executor": AGENT_GROUPS[group]["name"], "parallel": True},
            ))

        requested_keys = [item.key for item in request.elements]
        supervisor_id = "schema_supervisor"
        supervisor_started = time.monotonic()
        supervisor_callback = AgentExecutionCallback(
            request.run_id,
            supervisor_id,
            "schema-extraction-supervisor",
        )
        agent_log_store.event(
            request.run_id,
            supervisor_id,
            "supervisor.started",
            message="Schema Extraction Supervisor 开始并行调度子 Agent。",
            payload={
                "active_agents": [AGENT_GROUPS[group]["name"] for group in active_groups],
                "requested_fields": requested_keys,
                "framework": "deepagents",
            },
        )
        try:
            response = await supervisor.ainvoke({
                "messages": [{
                    "role": "user",
                    "content": json.dumps({
                        "active_agents": [AGENT_GROUPS[group]["name"] for group in active_groups],
                        "requested_keys": requested_keys,
                        "instruction": "立即在同一回合并行委派所有 active_agents，合并后返回结构化字段。",
                    }, ensure_ascii=False),
                }]
            }, config={"callbacks": [supervisor_callback]})
            payload = response.get("structured_response")
            if payload is None:
                payload = self._parse_message_response(response)
            elif isinstance(payload, dict):
                payload = AgentExtractionResponse.model_validate(payload)
            agent_log_store.event(
                request.run_id,
                supervisor_id,
                "supervisor.completed",
                message="Schema Extraction Supervisor 已完成合并。",
                payload={
                    "duration_ms": round((time.monotonic() - supervisor_started) * 1000),
                    "returned_fields": len(payload.fields),
                    "active_agent_count": len(active_groups),
                },
            )
        except Exception as error:
            agent_log_store.event(
                request.run_id,
                supervisor_id,
                "supervisor.failed",
                level="ERROR",
                message=str(error),
                payload={
                    "duration_ms": round((time.monotonic() - supervisor_started) * 1000),
                    "error_type": type(error).__name__,
                },
                exception="".join(traceback.format_exception(type(error), error, error.__traceback__)),
            )
            for group in active_groups:
                await progress(ExtractionProgress(group, "failed", [item.key for item in grouped[group]], {"error": str(error)}))
            raise RuntimeError(f"Deep Agents 字段抽取失败：{error}") from error

        normalized = self._normalize_fields(request.elements, payload.fields, source)
        for group in active_groups:
            group_keys = {item.key for item in grouped[group]}
            group_fields = [field for field in normalized if field.key in group_keys]
            await progress(ExtractionProgress(
                agent=group,
                state="completed",
                fields=sorted(group_keys),
                details={
                    "extracted": sum(field.status == "extracted" for field in group_fields),
                    "missing": sum(field.status == "missing" for field in group_fields),
                },
            ))

        extracted = sum(field.status == "extracted" for field in normalized)
        missing = sum(field.status == "missing" for field in normalized)
        with_evidence = sum(bool(field.evidence) for field in normalized if field.status == "extracted")
        metrics = {
            "requested": len(request.elements),
            "extracted": extracted,
            "missing": missing,
            "invalid": len(normalized) - extracted - missing,
            "evidence_coverage": round(with_evidence / extracted, 4) if extracted else 0.0,
            "agent_count": len(active_groups),
        }
        result = ExtractionResult(
            run_id=request.run_id,
            document_version_id=request.document_version_id,
            template={"id": request.template_id, "version": request.template_version},
            model={"provider": "qwen-compatible", "name": self.model_name, "framework": "deepagents"},
            agents=[AGENT_GROUPS[group]["name"] for group in active_groups],
            fields=normalized,
            metrics=metrics,
            source_truncated=truncated,
        )
        output_dir = self.artifact_root / request.run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / "schema_fields.json"
        result.artifact_path = str(artifact_path)
        artifact_path.write_text(result.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        return result

    def _build_source(self, request: ExtractionRequest) -> tuple[str, bool]:
        markdown = request.markdown_path.read_text(encoding="utf-8")
        structured = json.loads(request.structured_content_path.read_text(encoding="utf-8"))
        pages: list[str] = []
        for page in structured.get("pages") or []:
            page_idx = int(page.get("page_idx", len(pages)))
            chunks = [self._block_text(block) for block in page.get("blocks") or []]
            text = "\n".join(chunk for chunk in chunks if chunk.strip())
            pages.append(f"[PAGE {page_idx}]\n{text}")
        paginated = "\n\n".join(pages)
        source = f"# PAGINATED CONTENT\n{paginated}\n\n# MARKDOWN CONTENT\n{markdown}"
        if len(source) <= self.max_source_chars:
            return source, False
        return source[:self.max_source_chars], True

    @classmethod
    def _block_text(cls, block: Any) -> str:
        if isinstance(block, str):
            return block
        if isinstance(block, list):
            return "\n".join(cls._block_text(item) for item in block)
        if not isinstance(block, dict):
            return str(block) if block is not None else ""
        content = block.get("content") or block.get("text") or block.get("table_body") or ""
        return cls._block_text(content)

    @staticmethod
    def _group_elements(request: ExtractionRequest) -> dict[str, list[Any]]:
        grouped: dict[str, list[Any]] = {group: [] for group in AGENT_GROUPS}
        for element in request.elements:
            assigned = False
            for group, definition in AGENT_GROUPS.items():
                if any(element.key == prefix or element.key.startswith(prefix) for prefix in definition["prefixes"]):
                    grouped[group].append(element)
                    assigned = True
                    break
            if not assigned:
                grouped["research"].append(element)
        return grouped

    @staticmethod
    def _parse_message_response(response: dict[str, Any]) -> AgentExtractionResponse:
        messages = response.get("messages") or []
        content = messages[-1].content if messages else ""
        if isinstance(content, list):
            content = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
        match = re.search(r"\{.*\}", str(content), flags=re.DOTALL)
        if not match:
            raise ValueError("Supervisor 未返回结构化字段结果。")
        return AgentExtractionResponse.model_validate_json(match.group(0))

    @staticmethod
    def _normalize_fields(elements: list[Any], extracted: list[ExtractedField], source: str) -> list[ExtractedField]:
        candidates = {field.key: field for field in extracted}
        normalized_source = " ".join(source.split())
        result: list[ExtractedField] = []
        for element in elements:
            field = candidates.get(element.key)
            if not field:
                result.append(ExtractedField(
                    key=element.key,
                    label=element.label,
                    type=element.type,
                    status="missing",
                    value=[] if element.type == "list" else None,
                ))
                continue
            evidence = []
            for item in field.evidence:
                quote = " ".join(item.quote.split())
                if quote and quote in normalized_source:
                    evidence.append(Evidence(quote=item.quote, page_idx=item.page_idx, section=item.section))
            value = field.value
            valid_type = (
                (element.type == "list" and isinstance(value, list))
                or (element.type == "object" and isinstance(value, dict))
                or (element.type == "string" and isinstance(value, str))
            )
            has_value = valid_type and value not in (None, "", [], {})
            status = "extracted" if has_value else "missing"
            if field.status == "invalid" or (value not in (None, "", [], {}) and not valid_type):
                status = "invalid"
            result.append(ExtractedField(
                key=element.key,
                label=element.label,
                type=element.type,
                status=status,
                value=value if status != "missing" else ([] if element.type == "list" else None),
                confidence=max(0.0, min(1.0, field.confidence)),
                evidence=evidence,
            ))
        return result
