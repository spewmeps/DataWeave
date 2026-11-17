from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from dataweave.config import settings
from dataweave.schemas import ArtifactRoot, ArtifactTreeEntry, RunArtifactManifest, RunSnapshot
from dataweave.services.parsers.repository import ParseArtifactRepository
from dataweave.services.state_repository import StateRepository


@dataclass(frozen=True, slots=True)
class ArtifactRootSpec:
    id: str
    label: str
    description: str
    task_ids: tuple[str, ...]
    path: Path
    is_file: bool = False


class ArtifactBrowser:
    """Run-scoped artifact registry with opaque roots and traversal-safe file access."""

    def __init__(
        self,
        state_repository: StateRepository,
        parse_artifact_repository: ParseArtifactRepository,
    ) -> None:
        self.state_repository = state_repository
        self.parse_artifact_repository = parse_artifact_repository

    def manifest(self, snapshot: RunSnapshot) -> RunArtifactManifest:
        roots = [self._public_root(snapshot.id, spec) for spec in self._root_specs(snapshot)]
        return RunArtifactManifest(run_id=snapshot.id, roots=roots)

    def resolve_file(self, snapshot: RunSnapshot, root_id: str, relative_path: str) -> Path:
        spec = next((item for item in self._root_specs(snapshot) if item.id == root_id), None)
        if not spec:
            raise FileNotFoundError("产物目录不存在")
        normalized = PurePosixPath(relative_path)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("产物路径不合法")
        if spec.is_file:
            if relative_path != spec.path.name:
                raise FileNotFoundError("产物文件不存在")
            resolved = spec.path.resolve()
        else:
            root = spec.path.resolve()
            resolved = (root / Path(*normalized.parts)).resolve()
            if resolved != root and root not in resolved.parents:
                raise ValueError("产物路径超出运行目录")
        if not resolved.is_file():
            raise FileNotFoundError("产物文件不存在")
        return resolved

    def _root_specs(self, snapshot: RunSnapshot) -> list[ArtifactRootSpec]:
        specs: list[ArtifactRootSpec] = []
        source = self.state_repository.source_path_for_version(snapshot.document_version_id)
        if source and source.is_file():
            specs.append(
                ArtifactRootSpec(
                    id="source-document",
                    label="原始输入文档",
                    description="本次运行读取的不可变原始文件。",
                    task_ids=("receive", "parse", "parser_submit"),
                    path=source,
                    is_file=True,
                )
            )
        for record in self.parse_artifact_repository.list_for_run(snapshot.id):
            base_path = Path(record.base_path)
            if base_path.is_dir():
                specs.append(
                    ArtifactRootSpec(
                        id=f"parser-{record.id}",
                        label="解析器输出",
                        description="Parser 生成的 Markdown、JSON 和图片目录。",
                        task_ids=("parse", "parser_wait", "parser_persist", "document_json"),
                        path=base_path,
                    )
                )
        canonical = settings.data_dir / "canonical" / snapshot.document_version_id
        if canonical.is_dir():
            specs.append(
                ArtifactRootSpec(
                    id="canonical-document",
                    label="统一 Document JSON",
                    description="标准化后的 DataWeave Document JSON。",
                    task_ids=("document_json", "extract", "schema_merge"),
                    path=canonical,
                )
            )
        extraction = settings.extraction_dir / snapshot.id
        if extraction.is_dir():
            specs.append(
                ArtifactRootSpec(
                    id="schema-extraction",
                    label="Schema 提取结果",
                    description="Supervisor 与专业 Agent 合并后的结构化结果。",
                    task_ids=(
                        "extract", "schema_metadata", "schema_research", "schema_method",
                        "schema_experiment", "schema_merge",
                    ),
                    path=extraction,
                )
            )
        run_logs = settings.run_log_dir / snapshot.id
        if run_logs.is_dir():
            specs.append(
                ArtifactRootSpec(
                    id="run-logs",
                    label="运行与 Agent 日志",
                    description="本次运行产生的 JSONL 过程日志。",
                    task_ids=tuple(task.id for task in self._flatten(snapshot.tasks)),
                    path=run_logs,
                )
            )
        return specs

    def _public_root(self, run_id: str, spec: ArtifactRootSpec) -> ArtifactRoot:
        if spec.is_file:
            entries = [self._file_entry(run_id, spec.id, spec.path, spec.path.name)]
        else:
            entries = self._directory_entries(run_id, spec.id, spec.path, spec.path)
        return ArtifactRoot(
            id=spec.id,
            label=spec.label,
            description=spec.description,
            task_ids=list(spec.task_ids),
            entries=entries,
        )

    def _directory_entries(
        self,
        run_id: str,
        root_id: str,
        root: Path,
        directory: Path,
    ) -> list[ArtifactTreeEntry]:
        entries: list[ArtifactTreeEntry] = []
        try:
            children = sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.casefold()))
        except OSError:
            return entries
        for child in children:
            if child.is_symlink():
                continue
            relative = child.relative_to(root).as_posix()
            if child.is_dir():
                entries.append(
                    ArtifactTreeEntry(
                        name=child.name,
                        path=relative,
                        kind="directory",
                        children=self._directory_entries(run_id, root_id, root, child),
                    )
                )
            elif child.is_file():
                entries.append(self._file_entry(run_id, root_id, child, relative))
        return entries

    @staticmethod
    def _file_entry(run_id: str, root_id: str, path: Path, relative: str) -> ArtifactTreeEntry:
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = quote(relative, safe="")
        base_url = f"/api/runs/{run_id}/artifacts/{root_id}/content?path={encoded}"
        return ArtifactTreeEntry(
            name=path.name,
            path=relative,
            kind="file",
            size=path.stat().st_size,
            mime_type=mime_type,
            content_url=base_url,
            download_url=f"{base_url}&download=true",
        )

    @classmethod
    def _flatten(cls, tasks: list) -> list:
        return [task for parent in tasks for task in [parent, *cls._flatten(parent.children)]]
