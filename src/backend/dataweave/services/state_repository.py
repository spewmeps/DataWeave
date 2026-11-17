from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dataweave.config import settings
from dataweave.schemas import CreateRunRequest, RunSnapshot, UploadResponse


@dataclass(slots=True)
class StoredUpload:
    upload: UploadResponse
    source_path: Path


@dataclass(slots=True)
class StoredRun:
    snapshot: RunSnapshot
    request: CreateRunRequest
    source_path: Path
    events: list[dict[str, Any]]
    sequence: int


@dataclass(slots=True)
class IntegrationSetting:
    provider: str
    base_url: str
    api_key_ciphertext: str
    dataset_name: str
    dataset_id: str
    language: str
    parser_id: str
    status: str
    last_verified_at: str
    updated_at: str


class StateRepository:
    """SQLite persistence for the document registry and runtime snapshots.

    Source files and large parser outputs remain as local files. SQLite owns
    their durable locations plus the complete run/task/event state required to
    rebuild the UI after an API process restart.
    """

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS document_uploads (
                    upload_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    document_version_id TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    duplicate INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_document_uploads_sha256 "
                "ON document_uploads(sha256, created_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_runs (
                    id TEXT PRIMARY KEY,
                    snapshot_json TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    events_json TEXT NOT NULL,
                    sequence INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runtime_runs_created_at "
                "ON runtime_runs(created_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS integration_settings (
                    provider TEXT PRIMARY KEY,
                    base_url TEXT NOT NULL,
                    api_key_ciphertext TEXT NOT NULL,
                    dataset_name TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    parser_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_verified_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create_upload(self, upload: UploadResponse, source_path: Path) -> None:
        values = upload.model_dump(mode="json")
        values["duplicate"] = int(upload.duplicate)
        values["source_path"] = str(source_path.resolve())
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO document_uploads (
                    upload_id, document_id, document_version_id, filename,
                    size, sha256, duplicate, status, source_path, created_at
                ) VALUES (
                    :upload_id, :document_id, :document_version_id, :filename,
                    :size, :sha256, :duplicate, :status, :source_path, :created_at
                )
                """,
                values,
            )

    def get_upload(self, upload_id: str) -> StoredUpload | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM document_uploads WHERE upload_id = ?", (upload_id,)
            ).fetchone()
        return self._stored_upload(row) if row else None

    def get_upload_by_version(self, document_version_id: str) -> StoredUpload | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM document_uploads WHERE document_version_id = ?",
                (document_version_id,),
            ).fetchone()
        return self._stored_upload(row) if row else None

    def list_uploads(self) -> list[StoredUpload]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM document_uploads ORDER BY created_at DESC"
            ).fetchall()
        return [self._stored_upload(row) for row in rows]

    def find_document_id_by_sha256(self, sha256: str) -> str | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT document_id FROM document_uploads
                WHERE sha256 = ? ORDER BY created_at ASC LIMIT 1
                """,
                (sha256,),
            ).fetchone()
        return str(row["document_id"]) if row else None

    def source_path_for_version(self, document_version_id: str) -> Path | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT source_path FROM document_uploads WHERE document_version_id = ?",
                (document_version_id,),
            ).fetchone()
        return Path(row["source_path"]) if row else None

    def get_integration_setting(self, provider: str) -> IntegrationSetting | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM integration_settings WHERE provider = ?", (provider,)
            ).fetchone()
        return IntegrationSetting(**dict(row)) if row else None

    def save_integration_setting(self, setting: IntegrationSetting) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO integration_settings (
                    provider, base_url, api_key_ciphertext, dataset_name,
                    dataset_id, language, parser_id, status,
                    last_verified_at, updated_at
                ) VALUES (
                    :provider, :base_url, :api_key_ciphertext, :dataset_name,
                    :dataset_id, :language, :parser_id, :status,
                    :last_verified_at, :updated_at
                )
                ON CONFLICT(provider) DO UPDATE SET
                    base_url = excluded.base_url,
                    api_key_ciphertext = excluded.api_key_ciphertext,
                    dataset_name = excluded.dataset_name,
                    dataset_id = excluded.dataset_id,
                    language = excluded.language,
                    parser_id = excluded.parser_id,
                    status = excluded.status,
                    last_verified_at = excluded.last_verified_at,
                    updated_at = excluded.updated_at
                """,
                asdict(setting),
            )

    def save_run(
        self,
        snapshot: RunSnapshot,
        request: CreateRunRequest,
        source_path: Path,
        events: list[dict[str, Any]],
        sequence: int,
    ) -> None:
        values = {
            "id": snapshot.id,
            "snapshot_json": snapshot.model_dump_json(),
            "request_json": request.model_dump_json(),
            "source_path": str(source_path.resolve()),
            "events_json": json.dumps(events, ensure_ascii=False),
            "sequence": sequence,
            "created_at": snapshot.created_at,
            "updated_at": snapshot.last_activity_at,
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_runs (
                    id, snapshot_json, request_json, source_path, events_json,
                    sequence, created_at, updated_at
                ) VALUES (
                    :id, :snapshot_json, :request_json, :source_path, :events_json,
                    :sequence, :created_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    snapshot_json = excluded.snapshot_json,
                    request_json = excluded.request_json,
                    source_path = excluded.source_path,
                    events_json = excluded.events_json,
                    sequence = excluded.sequence,
                    updated_at = excluded.updated_at
                """,
                values,
            )

    def list_runs(self) -> list[StoredRun]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runtime_runs ORDER BY created_at ASC"
            ).fetchall()
        return [
            StoredRun(
                snapshot=RunSnapshot.model_validate_json(row["snapshot_json"]),
                request=CreateRunRequest.model_validate_json(row["request_json"]),
                source_path=Path(row["source_path"]),
                events=json.loads(row["events_json"] or "[]"),
                sequence=int(row["sequence"]),
            )
            for row in rows
        ]

    @staticmethod
    def _stored_upload(row: sqlite3.Row) -> StoredUpload:
        return StoredUpload(
            upload=UploadResponse(
                upload_id=row["upload_id"],
                document_id=row["document_id"],
                document_version_id=row["document_version_id"],
                filename=row["filename"],
                size=row["size"],
                sha256=row["sha256"],
                duplicate=bool(row["duplicate"]),
                status=row["status"],
                created_at=row["created_at"],
            ),
            source_path=Path(row["source_path"]),
        )


state_repository = StateRepository(settings.database_path)
