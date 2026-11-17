from dataweave.config import settings
from dataweave.services.extraction.deepagents_extractor import DeepAgentsSchemaExtractor
from dataweave.services.extraction.mock import MockSchemaExtractor


if settings.schema_extractor_mode == "mock":
    schema_extractor = MockSchemaExtractor()
else:
    schema_extractor = DeepAgentsSchemaExtractor(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        model_name=settings.dashscope_model,
        artifact_root=settings.extraction_dir,
        max_source_chars=settings.schema_extraction_max_source_chars,
        enable_thinking=settings.schema_extraction_enable_thinking,
        timeout_seconds=settings.schema_extraction_timeout_seconds,
    )
