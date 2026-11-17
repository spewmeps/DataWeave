from __future__ import annotations

from dataweave.config import settings
from dataweave.services.parsers.mineru import MinerUParser, MockMinerUTransport, RemoteMinerUTransport
from dataweave.services.parsers.repository import ParseArtifactRepository


artifact_repository = ParseArtifactRepository(settings.database_path)

if settings.parser_name != "mineru":
    raise RuntimeError(f"未注册的文档解析器：{settings.parser_name}")

if settings.mineru_mock:
    mineru_transport = MockMinerUTransport(settings.mineru_tier)
else:
    mineru_transport = RemoteMinerUTransport(
        api_url=settings.mineru_api_url,
        api_key=settings.mineru_api_key,
        model_version=settings.mineru_model_version,
        timeout_seconds=settings.mineru_timeout_seconds,
        poll_interval_seconds=settings.mineru_poll_interval_seconds,
    )

document_parser = MinerUParser(mineru_transport, artifact_repository, settings.artifact_dir)
