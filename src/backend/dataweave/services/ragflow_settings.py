from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken

from dataweave.config import settings
from dataweave.observability import application_logger
from dataweave.schemas import RagflowConfigurationResponse, RagflowConfigurationUpdate
from dataweave.services.state_repository import IntegrationSetting, StateRepository, state_repository


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
        record = self.repository.get_integration_setting("ragflow")
        if not record:
            return RagflowConfigurationResponse()
        api_key = self.cipher.decrypt(record.api_key_ciphertext)
        return RagflowConfigurationResponse(
            base_url=record.base_url,
            api_key_configured=True,
            api_key_masked=self._mask_key(api_key),
            dataset_name=record.dataset_name,
            dataset_id=record.dataset_id,
            language=record.language,
            parser_id=record.parser_id,
            status="connected" if record.status == "connected" else "error",
            last_verified_at=record.last_verified_at,
            updated_at=record.updated_at,
        )

    async def configure(self, request: RagflowConfigurationUpdate) -> RagflowConfigurationResponse:
        async with self._lock:
            previous = self.repository.get_integration_setting("ragflow")
            if request.api_key:
                api_key = request.api_key.strip()
            elif previous:
                api_key = self.cipher.decrypt(previous.api_key_ciphertext)
            else:
                raise RagflowApiError("首次配置必须填写 RAGFlow API Key", status_code=400)

            dataset_id, dataset_operation = await self.client.ensure_dataset(
                base_url=request.base_url,
                api_key=api_key,
                dataset_name=request.dataset_name,
                language=request.language,
                parser_id=request.parser_id,
            )
            now = datetime.now(UTC).isoformat()
            self.repository.save_integration_setting(
                IntegrationSetting(
                    provider="ragflow",
                    base_url=request.base_url,
                    api_key_ciphertext=self.cipher.encrypt(api_key),
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
                "RAGFlow configuration verified: base_url=%s dataset_id=%s dataset_name=%s",
                request.base_url,
                dataset_id,
                request.dataset_name,
            )
            return self.get().model_copy(update={"dataset_operation": dataset_operation})

    @staticmethod
    def _mask_key(value: str) -> str:
        suffix = value[-4:] if len(value) >= 4 else "****"
        return f"••••••••{suffix}"


ragflow_settings_service = RagflowSettingsService(state_repository)
