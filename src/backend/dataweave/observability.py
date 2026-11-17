from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from dataweave.config import settings


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def configure_file_logging() -> None:
    """Attach rotating local files without removing Uvicorn console handlers."""

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    resolved_path = str(settings.application_log_path.resolve())
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s [pid=%(process)d] %(message)s"
    )
    for logger_name in ("dataweave", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        already_configured = any(
            isinstance(handler, RotatingFileHandler)
            and str(Path(handler.baseFilename).resolve()) == resolved_path
            for handler in logger.handlers
        )
        if already_configured:
            continue
        handler = RotatingFileHandler(
            settings.application_log_path,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        handler.setLevel(settings.log_level)
        logger.addHandler(handler)
        logger.setLevel(settings.log_level)


class RunLogStore:
    """Append-only JSONL logs for one complete ingestion run."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lock = threading.RLock()
        self.directory.mkdir(parents=True, exist_ok=True)

    def path_for(self, run_id: str) -> Path:
        safe_id = "".join(character for character in run_id if character.isalnum() or character in {"-", "_"})
        if not safe_id or safe_id != run_id:
            raise ValueError("非法的 Run ID。")
        return self.directory / f"{safe_id}.log"

    def event(
        self,
        run_id: str,
        event_type: str,
        *,
        task_id: str | None = None,
        level: str = "INFO",
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        exception: str | None = None,
    ) -> None:
        entry = {
            "timestamp": utc_now(),
            "level": level,
            "run_id": run_id,
            "task_id": task_id,
            "event": event_type,
            "message": message,
            "payload": payload or {},
        }
        if exception:
            entry["exception"] = exception
        serialized = json.dumps(entry, ensure_ascii=False, default=str)
        path = self.path_for(run_id)
        with self._lock, path.open("a", encoding="utf-8") as target:
            target.write(serialized + "\n")


class AgentLogStore:
    """Append-only JSONL traces for Supervisor and individual extraction agents."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lock = threading.RLock()
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_identifier(value: str, label: str) -> str:
        safe = "".join(
            character
            for character in value
            if character.isalnum() or character in {"-", "_"}
        )
        if not safe or safe != value:
            raise ValueError(f"非法的 {label}。")
        return safe

    def path_for(self, run_id: str, agent_id: str) -> Path:
        safe_run_id = self._safe_identifier(run_id, "Run ID")
        safe_agent_id = self._safe_identifier(agent_id, "Agent ID")
        return self.directory / safe_run_id / "agents" / f"{safe_agent_id}.jsonl"

    def event(
        self,
        run_id: str,
        agent_id: str,
        event_type: str,
        *,
        level: str = "INFO",
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        exception: str | None = None,
    ) -> None:
        entry = {
            "timestamp": utc_now(),
            "level": level,
            "run_id": run_id,
            "agent_id": agent_id,
            "event": event_type,
            "message": message,
            "payload": payload or {},
        }
        if exception:
            entry["exception"] = exception
        serialized = json.dumps(entry, ensure_ascii=False, default=str)
        path = self.path_for(run_id, agent_id)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as target:
                target.write(serialized + "\n")


configure_file_logging()
run_log_store = RunLogStore(settings.run_log_dir)
agent_log_store = AgentLogStore(settings.agent_log_dir)
application_logger = logging.getLogger("dataweave")
