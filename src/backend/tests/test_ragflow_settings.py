from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from dataweave.main import app
from dataweave.schemas import RagflowConfigurationUpdate
from dataweave.services.ragflow_settings import CredentialCipher, RagflowHttpClient, RagflowSettingsService
from dataweave.services.state_repository import StateRepository


def test_configuration_creates_dataset_and_masks_encrypted_key(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer ragflow-secret-for-test"
        if request.method == "GET":
            return httpx.Response(200, json={"code": 0, "data": []})
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body == {
            "name": "DataWeave Papers",
            "language": "Chinese",
            "parse_type": 1,
            "parser_id": "paper",
            "permission": "me",
        }
        return httpx.Response(200, json={"code": 0, "data": {"id": "dataset_123", "name": body["name"]}})

    repository = StateRepository(tmp_path / "dataweave.db")
    service = RagflowSettingsService(
        repository,
        client=RagflowHttpClient(transport=httpx.MockTransport(handler)),
        cipher=CredentialCipher(tmp_path / "credentials.key"),
    )

    configured = asyncio.run(
        service.configure(
            RagflowConfigurationUpdate(
                base_url="http://ragflow.internal:18080/",
                api_key="ragflow-secret-for-test",
                dataset_name="DataWeave Papers",
            )
        )
    )

    assert configured.base_url == "http://ragflow.internal:18080"
    assert configured.dataset_id == "dataset_123"
    assert configured.status == "connected"
    assert configured.api_key_configured is True
    assert configured.api_key_masked == "••••••••test"
    assert len(requests) == 2

    stored = repository.get_integration_setting("ragflow")
    assert stored is not None
    assert "ragflow-secret-for-test" not in stored.api_key_ciphertext
    assert (tmp_path / "credentials.key").stat().st_mode & 0o777 == 0o600

    reopened = RagflowSettingsService(
        StateRepository(tmp_path / "dataweave.db"),
        client=RagflowHttpClient(transport=httpx.MockTransport(handler)),
        cipher=CredentialCipher(tmp_path / "credentials.key"),
    ).get()
    assert reopened.dataset_id == "dataset_123"
    assert reopened.api_key_masked == "••••••••test"


def test_configuration_reuses_exact_dataset_and_existing_key(tmp_path: Path) -> None:
    calls: list[str] = []

    def first_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"code": 0, "data": []})
        return httpx.Response(200, json={"code": 0, "data": {"id": "dataset_existing"}})

    repository = StateRepository(tmp_path / "dataweave.db")
    cipher = CredentialCipher(tmp_path / "credentials.key")
    service = RagflowSettingsService(
        repository,
        client=RagflowHttpClient(transport=httpx.MockTransport(first_handler)),
        cipher=cipher,
    )
    asyncio.run(
        service.configure(
            RagflowConfigurationUpdate(
                base_url="http://localhost:18080",
                api_key="ragflow-existing-key",
                dataset_name="Existing Knowledge",
            )
        )
    )

    def reuse_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        assert request.headers["Authorization"] == "Bearer ragflow-existing-key"
        return httpx.Response(
            200,
            json={"code": 0, "data": [{"id": "dataset_existing", "name": "Existing Knowledge"}]},
        )

    service.client = RagflowHttpClient(transport=httpx.MockTransport(reuse_handler))
    updated = asyncio.run(
        service.configure(
            RagflowConfigurationUpdate(
                base_url="http://localhost:18080",
                dataset_name="Existing Knowledge",
                language="Chinese",
                parser_id="paper",
            )
        )
    )
    assert updated.dataset_id == "dataset_existing"
    assert calls == ["GET"]


def test_storage_markers_are_present_on_core_api() -> None:
    response = TestClient(app).get("/api/templates/default")
    assert response.status_code == 200
    assert response.json()["storage_locations"][0]["service"] == "dataweave"
