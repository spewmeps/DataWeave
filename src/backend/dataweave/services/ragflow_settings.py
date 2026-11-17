from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, InvalidToken

from dataweave.config import settings
from dataweave.observability import application_logger
from dataweave.schemas import RagflowConfigurationResponse, RagflowConfigurationUpdate
from dataweave.services.state_repository import (
    IntegrationSetting,
    KnowledgeBaseConfiguration,
    StateRepository,
    state_repository,
)


class RagflowApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class CredentialCipher:
    """Encrypt local demo credentials without ever returning plaintext to the UI."""

    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path

    def _fernet(self) -> Fernet:
        configured_key = os.getenv("DATAWEAVE_CREDENTIAL_KEY", "").strip()
        if configured_key:
            key = configured_key.encode()
        else:
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.key_path.exists():
                self.key_path.write_bytes(Fernet.generate_key())
                self.key_path.chmod(0o600)
            key = self.key_path.read_bytes().strip()
        try:
            return Fernet(key)
        except (ValueError, TypeError) as error:
            raise RuntimeError("DATAWEAVE_CREDENTIAL_KEY 不是有效的 Fernet Key") from error

    def encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet().decrypt(value.encode()).decode()
        except InvalidToken as error:
            raise RuntimeError("无法解密已保存的 RAGFlow API Key，请重新配置") from error


class RagflowHttpClient:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def ensure_dataset(
        self,
        *,
        base_url: str,
        api_key: str,
        dataset_name: str,
        language: str,
        parser_id: str,
    ) -> tuple[str, str]:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        timeout = httpx.Timeout(20.0, connect=5.0)
        async with httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            transport=self.transport,
        ) as client:
            response = await self._request(
                client,
                "GET",
                "/api/v1/datasets",
                params={"page": 1, "page_size": 100, "name": dataset_name},
            )
            datasets = self._dataset_list(response)
            existing = next(
                (item for item in datasets if str(item.get("name", "")).casefold() == dataset_name.casefold()),
                None,
            )
            if existing:
                dataset_id = str(existing.get("id") or "")
                if dataset_id:
                    return dataset_id, "reused"

            created = await self._request(
                client,
                "POST",
                "/api/v1/datasets",
                json={
                    "name": dataset_name,
                    "language": language,
                    "parse_type": 1,
                    "parser_id": parser_id,
                    "permission": "me",
                },
            )
            data = created.get("data")
            if not isinstance(data, dict) or not data.get("id"):
                raise RagflowApiError("RAGFlow 创建知识库成功但未返回 dataset ID")
            return str(data["id"]), "created"

    @staticmethod
    async def _request(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await client.request(method, path, **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RagflowApiError("无法连接 RAGFlow，请检查 API 地址和网络状态") from error
        try:
            payload = response.json()
        except ValueError as error:
            raise RagflowApiError(f"RAGFlow 返回了无法解析的响应（HTTP {response.status_code}）") from error
        if response.status_code in {401, 403}:
            raise RagflowApiError("RAGFlow API Key 无效或没有知识库权限", status_code=400)
        if response.status_code >= 400:
            raise RagflowApiError(f"RAGFlow 请求失败（HTTP {response.status_code}）")
        if not isinstance(payload, dict):
            raise RagflowApiError("RAGFlow 返回格式不正确")
        code = payload.get("code", 0)
        if code not in {0, "0", None}:
            message = str(payload.get("message") or "RAGFlow 业务请求失败")
            raise RagflowApiError(message, status_code=400 if code in {100, 101, 102} else 502)
        return payload

    @staticmethod
    def _dataset_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data", [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            items = data.get("datasets") or data.get("items") or []
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []


class RagflowSettingsService:
    def __init__(
        self,
        repository: StateRepository,
        *,
        client: RagflowHttpClient | None = None,
        cipher: CredentialCipher | None = None,
    ) -> None:
        self.repository = repository
        self.client = client or RagflowHttpClient()
        self.cipher = cipher or CredentialCipher(settings.data_dir / "secrets" / "credentials.key")
        self._lock = asyncio.Lock()

    def get(self) -> RagflowConfigurationResponse:
        records = self.repository.list_knowledge_base_configurations("ragflow")
        if records:
            return self._response(records[0])
        return RagflowConfigurationResponse()

    def list(self) -> list[RagflowConfigurationResponse]:
        return [
            self._response(record)
            for record in self.repository.list_knowledge_base_configurations("ragflow")
        ]

    def get_by_id(self, configuration_id: str) -> RagflowConfigurationResponse | None:
        record = self.repository.get_knowledge_base_configuration(configuration_id)
        if not record or record.provider != "ragflow":
            return None
        return self._response(record)

    def _response(self, record: KnowledgeBaseConfiguration) -> RagflowConfigurationResponse:
        api_key = self.cipher.decrypt(record.api_key_ciphertext)
        return RagflowConfigurationResponse(
            id=record.id,
            base_url=record.base_url,
            api_key_configured=True,
            api_key_masked=self._mask_key(api_key),
            dataset_name=record.dataset_name,
            dataset_id=record.dataset_id,
            language=record.language,
            parser_id=record.parser_id,
            status="connected" if record.status == "connected" else "error",
            last_verified_at=record.last_verified_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def configure(
        self,
        request: RagflowConfigurationUpdate,
        *,
        configuration_id: str | None = None,
    ) -> RagflowConfigurationResponse:
        async with self._lock:
            previous = (
                self.repository.get_knowledge_base_configuration(configuration_id)
                if configuration_id
                else None
            )
            if not configuration_id:
                previous = next(
                    (
                        item
                        for item in self.repository.list_knowledge_base_configurations("ragflow")
                        if item.base_url == request.base_url
                        and item.dataset_name.casefold() == request.dataset_name.casefold()
                    ),
                    None,
                )
            if configuration_id and (not previous or previous.provider != "ragflow"):
                raise RagflowApiError("知识库配置不存在", status_code=404)
            if request.api_key:
                api_key = request.api_key.strip()
            elif previous:
                api_key = self.cipher.decrypt(previous.api_key_ciphertext)
            else:
                raise RagflowApiError("新增知识库配置必须填写 RAGFlow API Key", status_code=400)

            dataset_id, dataset_operation = await self.client.ensure_dataset(
                base_url=request.base_url,
                api_key=api_key,
                dataset_name=request.dataset_name,
                language=request.language,
                parser_id=request.parser_id,
            )
            now = datetime.now(UTC).isoformat()
            matching = next(
                (
                    item
                    for item in self.repository.list_knowledge_base_configurations("ragflow")
                    if item.base_url == request.base_url and item.dataset_id == dataset_id
                ),
                None,
            )
            if matching and configuration_id and matching.id != configuration_id:
                raise RagflowApiError("该 RAGFlow 知识库已经存在于配置列表中", status_code=409)
            target_id = configuration_id or (matching.id if matching else f"kb_{uuid4().hex[:16]}")
            created_at = previous.created_at if previous else matching.created_at if matching else now
            encrypted_key = self.cipher.encrypt(api_key)
            self.repository.save_knowledge_base_configuration(
                KnowledgeBaseConfiguration(
                    id=target_id,
                    provider="ragflow",
                    base_url=request.base_url,
                    api_key_ciphertext=encrypted_key,
                    dataset_name=request.dataset_name,
                    dataset_id=dataset_id,
                    language=request.language,
                    parser_id=request.parser_id,
                    status="connected",
                    last_verified_at=now,
                    created_at=created_at,
                    updated_at=now,
                )
            )
            # Keep the original singleton synchronized for backward-compatible callers.
            self.repository.save_integration_setting(
                IntegrationSetting(
                    provider="ragflow",
                    base_url=request.base_url,
                    api_key_ciphertext=encrypted_key,
                    dataset_name=request.dataset_name,
                    dataset_id=dataset_id,
                    language=request.language,
                    parser_id=request.parser_id,
                    status="connected",
                    last_verified_at=now,
                    updated_at=now,
                )
            )
            application_logger.info(
                "RAGFlow configuration verified: configuration_id=%s base_url=%s dataset_id=%s dataset_name=%s",
                target_id,
                request.base_url,
                dataset_id,
                request.dataset_name,
            )
            saved = self.get_by_id(target_id)
            if not saved:
                raise RuntimeError("知识库配置保存后无法读取")
            return saved.model_copy(update={"dataset_operation": dataset_operation})

    @staticmethod
    def _mask_key(value: str) -> str:
        suffix = value[-4:] if len(value) >= 4 else "****"
        return f"••••••••{suffix}"


ragflow_settings_service = RagflowSettingsService(state_repository)
