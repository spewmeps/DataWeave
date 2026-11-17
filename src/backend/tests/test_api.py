from __future__ import annotations

import io
import json
import time
import zipfile

from fastapi.testclient import TestClient

import dataweave.services.run_manager as run_manager_module
from dataweave.main import app
from dataweave.services.parsers.base import ParseProgress
from dataweave.services.parsers.mineru import RemoteMinerUTransport


client = TestClient(app)


def test_mineru_cloud_zip_is_normalized() -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("paper/full.md", "# Demo\n")
        archive.writestr(
            "paper/paper_content_list.json",
            json.dumps([
                {"type": "text", "text": "Demo", "page_idx": 0},
                {"type": "table", "table_body": "| A |", "page_idx": 1},
            ]),
        )
        archive.writestr(
            "paper/paper_content_list_v2.json",
            json.dumps([[{"type": "text", "content": "Nested v2 must not replace the flat list"}]]),
        )
        archive.writestr("paper/images/figure.png", b"mock-image")
    transport = RemoteMinerUTransport("https://mineru.net", "test-token", "vlm", 60, 1)
    result = transport._read_result_zip(archive_bytes.getvalue(), "paper.pdf")
    assert result.markdown == "# Demo\n"
    assert result.middle_json["schema"] == "dataweave.normalized-middle"
    assert len(result.structured_content["pages"]) == 2
    assert result.metadata["tables"] == 1
    assert set(result.images) == {"figure.png"}


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_default_template_contains_paper_metadata() -> None:
    response = client.get("/api/templates/default")
    assert response.status_code == 200
    keys = {element["key"] for element in response.json()["elements"]}
    assert {
        "paper.authors",
        "paper.affiliations",
        "paper.publication_date",
        "paper.author_keywords",
        "research.domain_keywords",
        "research.innovation_keywords",
    } <= keys
    assert response.json()["version"] == 3


def test_upload_and_create_run() -> None:
    with TestClient(app) as live_client:
        upload = live_client.post(
            "/api/uploads",
            files={"file": ("paper.pdf", io.BytesIO(b"%PDF-1.7\nmock"), "application/pdf")},
        )
        assert upload.status_code == 201
        stored = upload.json()
        assert stored["storage_locations"][0]["backend"] == "local_filesystem"
        created = live_client.post(
            "/api/ingestion-runs",
            json={
                "document_id": stored["document_id"],
                "document_version_id": stored["document_version_id"],
                "document_name": stored["filename"],
                "template_id": "paper_analysis",
                "template_version": 3,
                "enabled_elements": ["paper.title", "paper.authors"],
            },
        )
        assert created.status_code == 202
        snapshot = live_client.get(created.json()["links"]["self"])
        assert snapshot.status_code == 200
        assert snapshot.json()["document_name"] == "paper.pdf"
        assert snapshot.json()["storage_locations"][0]["backend"] == "sqlite"
        tasks = snapshot.json()["tasks"]
        materialize = next(task for task in tasks if task["id"] == "materialize")
        assert {child["id"] for child in materialize["children"]} == {
            "page_index",
            "graph",
            "tree",
            "hybrid_retrieval",
        }
        assert any(task["id"] == "document_json" for task in tasks)
        documents = live_client.get("/api/documents")
        assert documents.status_code == 200
        listed = next(item for item in documents.json() if item["document_version_id"] == stored["document_version_id"])
        assert listed["filename"] == "paper.pdf"
        assert listed["run_id"] == created.json()["run_id"]
        assert listed["storage_locations"][0]["service"] == "dataweave"

        run_id = created.json()["run_id"]
        final = snapshot.json()
        for _ in range(80):
            final = live_client.get(f"/api/runs/{run_id}").json()
            if final["status"] in {"awaiting_review", "failed"}:
                break
            time.sleep(0.1)
        assert final["status"] == "awaiting_review"

        parse_task = next(task for task in final["tasks"] if task["id"] == "parse")
        assert parse_task["status"] == "completed"
        assert {child["id"] for child in parse_task["children"]} == {
            "parser_submit",
            "parser_wait",
            "parser_persist",
        }
        assert all(child["status"] == "completed" for child in parse_task["children"])
        receive_task = next(task for task in final["tasks"] if task["id"] == "receive")
        assert receive_task["input"]["document_version_id"] == stored["document_version_id"]
        assert receive_task["input"]["filename"] == "paper.pdf"

        extraction_task = next(task for task in final["tasks"] if task["id"] == "extract")
        assert extraction_task["executor"] == "DeepAgentsSchemaMapper"
        assert {child["id"] for child in extraction_task["children"]} == {
            "schema_metadata",
            "schema_research",
            "schema_method",
            "schema_experiment",
            "schema_merge",
        }
        assert {field["key"] for field in extraction_task["output"]["fields"]} == {
            "paper.title",
            "paper.authors",
        }
        assert extraction_task["output"]["model"]["framework"] == "deepagents-contract"

        artifacts = live_client.get(f"/api/runs/{run_id}/parse-artifacts")
        assert artifacts.status_code == 200
        artifact = artifacts.json()[0]
        assert artifact["parser_name"] == "mineru"
        assert artifact["status"] == "completed"
        assert artifact["progress"] == 100
        assert set(artifact["file_urls"]) == {"markdown", "middle_json", "structured_content"}

        markdown = live_client.get(artifact["file_urls"]["markdown"])
        assert markdown.status_code == 200
        assert "MinerU Mock Transport" in markdown.text
        middle_json = live_client.get(artifact["file_urls"]["middle_json"])
        assert middle_json.status_code == 200
        assert middle_json.json()["schema"] == "docvortex.middle"
        assert middle_json.json()["schema_version"] == "2.0"

        manifest = live_client.get(f"/api/runs/{run_id}/artifacts")
        assert manifest.status_code == 200
        roots = {root["id"]: root for root in manifest.json()["roots"]}
        assert {"source-document", "canonical-document", "schema-extraction"} <= roots.keys()
        canonical_file = next(
            entry for entry in roots["canonical-document"]["entries"]
            if entry["name"] == "document.json"
        )
        assert canonical_file["mime_type"] == "application/json"
        canonical_content = live_client.get(canonical_file["content_url"])
        assert canonical_content.status_code == 200
        assert canonical_content.json()["schema"] == "dataweave.document.v1"
        download = live_client.get(canonical_file["download_url"])
        assert "attachment" in download.headers["content-disposition"]
        traversal = live_client.get(
            f"/api/runs/{run_id}/artifacts/canonical-document/content",
            params={"path": "../dataweave.db"},
        )
        assert traversal.status_code == 400

        run_log = live_client.get(f"/api/runs/{run_id}/logs")
        assert run_log.status_code == 200
        assert '"event": "run.created"' in run_log.text
        assert '"event": "task.completed"' in run_log.text

        agent_log = live_client.get(f"/api/runs/{run_id}/agents/schema_metadata/logs")
        assert agent_log.status_code == 200
        assert '"agent_id": "schema_metadata"' in agent_log.text
        assert '"event": "orchestrator.state"' in agent_log.text

        agent_trace = live_client.get(f"/api/runs/{run_id}/agents/schema_metadata/trace")
        assert agent_trace.status_code == 200
        trace_body = agent_trace.json()
        assert trace_body["agent_id"] == "schema_metadata"
        assert trace_body["events"]
        assert {field["key"] for field in trace_body["result"]["fields"]} == {
            "paper.title",
            "paper.authors",
        }
        assert trace_body["result"]["field_count"] == 2

        missing_agent = live_client.get(f"/api/runs/{run_id}/agents/schema_unknown/logs")
        assert missing_agent.status_code == 404

        repeated = live_client.post(f"/api/runs/{run_id}/retry")
        assert repeated.status_code == 202
        repeated_snapshot = live_client.get(repeated.json()["links"]["self"]).json()
        assert repeated_snapshot["retry_of_run_id"] == run_id
        assert repeated_snapshot["retry_number"] == 1


def test_failed_run_can_be_retried(monkeypatch) -> None:
    original_parser = run_manager_module.document_parser

    class FailOnceParser:
        calls = 0

        async def parse(self, request, progress):
            self.calls += 1
            if self.calls == 1:
                await progress(ParseProgress("submit", "running", 5, "正在提交远程解析任务"))
                raise RuntimeError("模拟远程解析失败")
            return await original_parser.parse(request, progress)

    monkeypatch.setattr(run_manager_module, "document_parser", FailOnceParser())

    with TestClient(app) as live_client:
        upload = live_client.post(
            "/api/uploads",
            files={"file": ("retry-paper.pdf", io.BytesIO(b"%PDF-1.7\nretry"), "application/pdf")},
        )
        stored = upload.json()
        created = live_client.post(
            "/api/ingestion-runs",
            json={
                "document_id": stored["document_id"],
                "document_version_id": stored["document_version_id"],
                "document_name": stored["filename"],
                "enabled_elements": ["paper.title"],
            },
        ).json()
        failed_run_id = created["run_id"]

        failed = {}
        for _ in range(40):
            failed = live_client.get(f"/api/runs/{failed_run_id}").json()
            if failed["status"] == "failed":
                break
            time.sleep(0.05)
        assert failed["status"] == "failed"
        parse_task = next(task for task in failed["tasks"] if task["id"] == "parse")
        child_statuses = {child["id"]: child["status"] for child in parse_task["children"]}
        assert child_statuses == {
            "parser_submit": "failed",
            "parser_wait": "cancelled",
            "parser_persist": "cancelled",
        }
        assert failed["progress"]["current_task"] is None
        assert all(task["status"] == "cancelled" for task in failed["tasks"][2:])

        retried = live_client.post(f"/api/runs/{failed_run_id}/retry")
        assert retried.status_code == 202
        retry_run_id = retried.json()["run_id"]
        assert retry_run_id != failed_run_id

        retry_snapshot = live_client.get(f"/api/runs/{retry_run_id}").json()
        assert retry_snapshot["retry_of_run_id"] == failed_run_id
        assert retry_snapshot["retry_number"] == 1

        for _ in range(80):
            retry_snapshot = live_client.get(f"/api/runs/{retry_run_id}").json()
            if retry_snapshot["status"] in {"awaiting_review", "failed"}:
                break
            time.sleep(0.1)
        assert retry_snapshot["status"] == "awaiting_review"


def test_stored_document_can_start_without_existing_run() -> None:
    with TestClient(app) as live_client:
        upload = live_client.post(
            "/api/uploads",
            files={"file": ("manual-start.pdf", io.BytesIO(b"%PDF-1.7\nmanual"), "application/pdf")},
        ).json()

        created = live_client.post(f"/api/documents/{upload['document_version_id']}/runs")
        assert created.status_code == 202
        snapshot = live_client.get(created.json()["links"]["self"]).json()
        assert snapshot["document_version_id"] == upload["document_version_id"]

        active_conflict = live_client.post(f"/api/documents/{upload['document_version_id']}/runs")
        assert active_conflict.status_code == 409


def test_unexpected_stage_failure_stops_all_downstream_tasks(monkeypatch) -> None:
    def fail_compilation(parse_result, request):
        del parse_result, request
        raise RuntimeError("模拟 Document JSON 编译失败")

    monkeypatch.setattr(
        run_manager_module.RunManager,
        "_compile_document_json",
        staticmethod(fail_compilation),
    )

    with TestClient(app) as live_client:
        upload = live_client.post(
            "/api/uploads",
            files={"file": ("fail-fast.pdf", io.BytesIO(b"%PDF-1.7\nfail-fast"), "application/pdf")},
        ).json()
        created = live_client.post(
            "/api/ingestion-runs",
            json={
                "document_id": upload["document_id"],
                "document_version_id": upload["document_version_id"],
                "document_name": upload["filename"],
            },
        ).json()

        snapshot = {}
        for _ in range(40):
            snapshot = live_client.get(f"/api/runs/{created['run_id']}").json()
            if snapshot["status"] == "failed":
                break
            time.sleep(0.05)

        assert snapshot["status"] == "failed"
        document_json = next(task for task in snapshot["tasks"] if task["id"] == "document_json")
        assert document_json["status"] == "failed"
        downstream = snapshot["tasks"][3:]
        assert downstream
        assert all(task["status"] == "cancelled" for task in downstream)
        assert snapshot["progress"]["current_task"] is None

