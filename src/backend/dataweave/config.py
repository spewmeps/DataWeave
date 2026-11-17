from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Load ignored local credentials before constructing the immutable application settings.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


# Runtime data belongs to the local project workspace instead of /tmp so an
# API process restart (or host cleanup of temporary files) cannot erase it.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / ".data"


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "DataWeave API"
    api_prefix: str = "/api"
    max_upload_bytes: int = 50 * 1024 * 1024
    data_dir: Path = Path(os.getenv("DATAWEAVE_DATA_DIR") or str(DEFAULT_DATA_DIR)).expanduser().resolve()
    parser_name: str = os.getenv("DATAWEAVE_PARSER", "mineru")
    mineru_mock: bool = env_bool("MINERU_MOCK", True)
    mineru_api_url: str = os.getenv("MINERU_API_URL", "https://mineru.net")
    mineru_api_key: str = os.getenv("MINERU_API_KEY", "")
    mineru_tier: str = os.getenv("MINERU_TIER", "standard")
    mineru_model_version: str = os.getenv("MINERU_MODEL_VERSION", "vlm")
    mineru_poll_interval_seconds: float = float(os.getenv("MINERU_POLL_INTERVAL_SECONDS", "1.0"))
    mineru_timeout_seconds: float = float(os.getenv("MINERU_TIMEOUT_SECONDS", "600"))
    schema_extractor_mode: str = os.getenv("SCHEMA_EXTRACTOR_MODE", "mock")
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://maas.qianwenaiapi.com/compatible-mode/v1",
    )
    dashscope_model: str = os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash")
    schema_extraction_max_source_chars: int = int(os.getenv("SCHEMA_EXTRACTION_MAX_SOURCE_CHARS", "120000"))
    schema_extraction_enable_thinking: bool = env_bool("SCHEMA_EXTRACTION_ENABLE_THINKING", True)
    schema_extraction_timeout_seconds: float = float(os.getenv("SCHEMA_EXTRACTION_TIMEOUT_SECONDS", "300"))
    log_level: str = os.getenv("DATAWEAVE_LOG_LEVEL", "INFO").upper()
    log_max_bytes: int = int(os.getenv("DATAWEAVE_LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    log_backup_count: int = int(os.getenv("DATAWEAVE_LOG_BACKUP_COUNT", "5"))
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def artifact_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "dataweave.db"

    @property
    def extraction_dir(self) -> Path:
        return self.data_dir / "extractions"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def application_log_path(self) -> Path:
        return self.log_dir / "application.log"

    @property
    def run_log_dir(self) -> Path:
        return self.log_dir / "runs"

    @property
    def agent_log_dir(self) -> Path:
        # Each run owns an agents/ directory below this root. Keeping Agent
        # traces next to the run log makes a failed execution self-contained.
        return self.run_log_dir


settings = Settings()

