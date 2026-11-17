from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class ParseArtifactRecord:
    id: str
    run_id: str
    document_id: str
    document_version_id: str
    parser_name: str
    parser_version: str
    provider_task_id: str | None
    status: str
    progress: int
    base_path: str
    markdown_path: str
    middle_json_path: str
    structured_content_path: str
    images_path: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class ParseArtifactRepository:
    """Small SQLite repository; large parser outputs remain in the artifact store."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS parse_artifacts (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    document_version_id TEXT NOT NULL,
                    parser_name TEXT NOT NULL,
                    parser_version TEXT NOT NULL,
                    provider_task_id TEXT,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    base_path TEXT NOT NULL,
                    markdown_path TEXT NOT NULL,
                    middle_json_path TEXT NOT NULL,
                    structured_content_path TEXT NOT NULL,
                    images_path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_parse_artifacts_run ON parse_artifacts(run_id)")

    def create(self, record: ParseArtifactRecord) -> None:
        values = asdict(record)
        values["metadata_json"] = json.dumps(values.pop("metadata"), ensure_ascii=False)
        columns = ", ".join(values)
        placeholders = ", ".join(f":{column}" for column in values)
        with self._lock, self._connect() as connection:
            connection.execute(f"INSERT INTO parse_artifacts ({columns}) VALUES ({placeholders})", values)

    def update(self, artifact_id: str, **changes: Any) -> None:
        if not changes:
            return
        changes["updated_at"] = utc_now()
        if "metadata" in changes:
            changes["metadata_json"] = json.dumps(changes.pop("metadata"), ensure_ascii=False)
        assignments = ", ".join(f"{key} = :{key}" for key in changes)
        changes["artifact_id"] = artifact_id
        with self._lock, self._connect() as connection:
            connection.execute(f"UPDATE parse_artifacts SET {assignments} WHERE id = :artifact_id", changes)

    def get(self, artifact_id: str) -> ParseArtifactRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM parse_artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return self._from_row(row) if row else None

    def list_for_run(self, run_id: str) -> list[ParseArtifactRecord]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM parse_artifacts WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ParseArtifactRecord:
        return ParseArtifactRecord(
            id=row["id"],
            run_id=row["run_id"],
            document_id=row["document_id"],
            document_version_id=row["document_version_id"],
            parser_name=row["parser_name"],
            parser_version=row["parser_version"],
            provider_task_id=row["provider_task_id"],
            status=row["status"],
            progress=row["progress"],
            base_path=row["base_path"],
            markdown_path=row["markdown_path"],
            middle_json_path=row["middle_json_path"],
            structured_content_path=row["structured_content_path"],
            images_path=row["images_path"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
