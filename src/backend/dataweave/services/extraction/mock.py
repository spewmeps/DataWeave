from __future__ import annotations

from dataweave.services.extraction.base import (
    ExtractedField,
    ExtractionProgress,
    ExtractionRequest,
    ExtractionResult,
    ProgressCallback,
)
from dataweave.services.extraction.deepagents_extractor import AGENT_GROUPS


class MockSchemaExtractor:
    """Explicit test-only extractor; production never falls back to it silently."""

    async def extract(self, request: ExtractionRequest, progress: ProgressCallback) -> ExtractionResult:
        agents = []
        for group, definition in AGENT_GROUPS.items():
            keys = [element.key for element in request.elements if any(
                element.key == prefix or element.key.startswith(prefix) for prefix in definition["prefixes"]
            )]
            if not keys:
                continue
            agents.append(definition["name"])
            await progress(ExtractionProgress(group, "running", keys, {"parallel": True, "mode": "mock"}))
            await progress(ExtractionProgress(group, "completed", keys, {"extracted": 0, "missing": len(keys)}))
        fields = [ExtractedField(
            key=element.key,
            label=element.label,
            type=element.type,
            status="missing",
            value=[] if element.type == "list" else None,
        ) for element in request.elements]
        return ExtractionResult(
            run_id=request.run_id,
            document_version_id=request.document_version_id,
            template={"id": request.template_id, "version": request.template_version},
            model={"provider": "test", "name": "mock", "framework": "deepagents-contract"},
            agents=agents,
            fields=fields,
            metrics={
                "requested": len(fields), "extracted": 0, "missing": len(fields),
                "invalid": 0, "evidence_coverage": 0.0, "agent_count": len(agents),
            },
        )
