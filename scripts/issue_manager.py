#!/usr/bin/env python3
"""Manage GitHub issues from a formatted Markdown manifest.

The manifest is authoritative for title, body, state, labels, and assignees.
Remote writes require an explicit ``--apply`` flag.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "issues" / "issues.md"
DEFAULT_REPO = os.environ.get("DATAWEAVE_ISSUE_REPO", "spewmeps/DataWeave")
MANAGED_FOOTER = "<!-- managed-by: scripts/issue_manager.py -->"
MANAGED_KEY_PATTERN = re.compile(r"稳定标识：`(?P<key>[A-Z][A-Z0-9-]+)`。")
ISSUE_PATTERN = re.compile(
    r"^## \[(?P<key>[A-Z][A-Z0-9-]+)\] (?P<title>[^\n]+)\n"
    r"(?P<meta><!-- issue: (?P<attrs>[^\n]+) -->)\n"
    r"<!-- issue-body -->\n(?P<body>.*?)\n<!-- /issue-body -->",
    re.MULTILINE | re.DOTALL,
)
INDEX_PATTERN = re.compile(
    r"<!-- issue-index:start -->.*?<!-- issue-index:end -->",
    re.DOTALL,
)


@dataclass(frozen=True)
class IssueSpec:
    key: str
    title: str
    number: int | None
    state: str
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    body: str

    @property
    def remote_body(self) -> str:
        return f"{self.body.strip()}\n\n---\n{MANAGED_FOOTER}\n本 Issue 由 `issues/issues.md` 管理，稳定标识：`{self.key}`。"


def fail(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(command: list[str], *, stdin: str | None = None, capture: bool = True) -> str:
    process = subprocess.run(
        command,
        cwd=ROOT,
        input=stdin,
        text=True,
        capture_output=capture,
        check=False,
    )
    if process.returncode:
        detail = (process.stderr or process.stdout or "command failed").strip()
        fail(f"{' '.join(command)}\n{detail}")
    return process.stdout.strip() if capture else ""


def require_tools() -> None:
    run(["git", "--version"])
    run(["gh", "--version"])
    run(["gh", "auth", "status"])


def parse_attrs(raw: str, key: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            fail(f"{key}: metadata fragment must use name=value: {part!r}")
        name, value = part.split("=", 1)
        result[name.strip()] = value.strip()
    required = {"number", "state", "labels", "assignees"}
    missing = required - result.keys()
    if missing:
        fail(f"{key}: missing metadata fields: {', '.join(sorted(missing))}")
    unknown = result.keys() - required
    if unknown:
        fail(f"{key}: unsupported metadata fields: {', '.join(sorted(unknown))}")
    return result


def split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def load_manifest(path: Path) -> tuple[str, list[IssueSpec]]:
    if not path.is_file():
        fail(f"manifest not found: {path}")
    text = path.read_text(encoding="utf-8")
    specs: list[IssueSpec] = []
    keys: set[str] = set()
    numbers: set[int] = set()
    for match in ISSUE_PATTERN.finditer(text):
        key = match.group("key")
        attrs = parse_attrs(match.group("attrs"), key)
        number_text = attrs["number"]
        if number_text and not number_text.isdigit():
            fail(f"{key}: number must be empty or a positive integer")
        number = int(number_text) if number_text else None
        if attrs["state"] not in {"open", "closed"}:
            fail(f"{key}: state must be open or closed")
        if key in keys:
            fail(f"duplicate issue key: {key}")
        if number is not None and number in numbers:
            fail(f"duplicate GitHub issue number: #{number}")
        keys.add(key)
        if number is not None:
            numbers.add(number)
        specs.append(
            IssueSpec(
                key=key,
                title=match.group("title").strip(),
                number=number,
                state=attrs["state"],
                labels=split_csv(attrs["labels"]),
                assignees=split_csv(attrs["assignees"]),
                body=match.group("body").strip(),
            )
        )
    if not specs:
        fail("manifest contains no issue blocks")
    return text, specs


def issue_kind(spec: IssueSpec) -> str:
    if "bug" in spec.labels:
        return "Bug"
    if "tech-debt" in spec.labels:
        return "Tech Debt"
    if "documentation" in spec.labels:
        return "Docs"
    return "Feature"


def label_value(spec: IssueSpec, prefix: str, fallback: str = "—") -> str:
    label = next((item for item in spec.labels if item.startswith(prefix)), "")
    return label.split(":", 1)[1] if ":" in label else fallback


def render_index(specs: list[IssueSpec], repo: str) -> str:
    rows = [
        "<!-- issue-index:start -->",
        "| Key | GitHub | 类型 | 优先级 | 模块 | 状态 | 标题 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for spec in specs:
        github = f"[#{spec.number}](https://github.com/{repo}/issues/{spec.number})" if spec.number else "待创建"
        state = "Open" if spec.state == "open" else "Closed"
        title = spec.title.replace("|", "\\|")
        rows.append(
            f"| `{spec.key}` | {github} | {issue_kind(spec)} | "
            f"{label_value(spec, 'priority:')} | {label_value(spec, 'area:')} | {state} | {title} |"
        )
    rows.append("<!-- issue-index:end -->")
    return "\n".join(rows)


def write_index(path: Path, repo: str) -> None:
    text, specs = load_manifest(path)
    index = render_index(specs, repo)
    if not INDEX_PATTERN.search(text):
        fail("manifest is missing issue-index markers")
    updated = INDEX_PATTERN.sub(index, text, count=1)
    path.write_text(updated, encoding="utf-8")
    print(f"updated index: {path.relative_to(ROOT)} ({len(specs)} issues)")


def update_number(path: Path, key: str, number: int) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(^## \[{re.escape(key)}\][^\n]*\n<!-- issue: )number=[^;]*(;)",
        re.MULTILINE,
    )
    updated, count = pattern.subn(rf"\g<1>number={number}\g<2>", text, count=1)
    if count != 1:
        fail(f"could not update issue number for {key}")
    path.write_text(updated, encoding="utf-8")


def gh_json(command: list[str], *, stdin: str | None = None) -> Any:
    output = run(command, stdin=stdin)
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        fail(f"GitHub CLI returned invalid JSON: {error}")


def get_remote_issue(repo: str, number: int) -> dict[str, Any]:
    return gh_json(
        [
            "gh", "issue", "view", str(number), "--repo", repo,
            "--json", "number,title,body,state,labels,assignees,url",
        ]
    )


def managed_key_from_body(body: str | None) -> str | None:
    """Return the stable manifest key embedded in a managed issue body."""
    if not body or MANAGED_FOOTER not in body:
        return None
    match = MANAGED_KEY_PATTERN.search(body)
    return match.group("key") if match else None


def get_remote_managed_issues(repo: str) -> dict[str, dict[str, Any]]:
    """Index all remotely managed issues by stable key.

    This reconciliation is deliberately performed before creating numberless
    manifest entries. If a previous POST succeeded on GitHub but its response
    timed out locally, the next sync recovers the issue number instead of
    creating a duplicate.
    """
    managed: dict[str, dict[str, Any]] = {}
    page = 1
    while True:
        issues = gh_json(
            [
                "gh", "api",
                f"repos/{repo}/issues?state=all&per_page=100&page={page}",
            ]
        )
        if not isinstance(issues, list):
            fail("GitHub issues API returned an unexpected response")
        for issue in issues:
            if issue.get("pull_request"):
                continue
            key = managed_key_from_body(issue.get("body"))
            if not key:
                continue
            previous = managed.get(key)
            if previous and previous.get("number") != issue.get("number"):
                fail(
                    f"remote duplicate managed key {key}: "
                    f"#{previous.get('number')} and #{issue.get('number')}; "
                    "resolve the duplicate before syncing"
                )
            managed[key] = issue
        if len(issues) < 100:
            break
        page += 1
    return managed


def normalized_remote(remote: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": remote.get("title", ""),
        "body": (remote.get("body") or "").strip(),
        "state": str(remote.get("state", "")).lower(),
        "labels": sorted(label["name"] for label in remote.get("labels", [])),
        "assignees": sorted(user["login"] for user in remote.get("assignees", [])),
    }


def desired(spec: IssueSpec) -> dict[str, Any]:
    return {
        "title": spec.title,
        "body": spec.remote_body.strip(),
        "state": spec.state,
        "labels": sorted(spec.labels),
        "assignees": sorted(spec.assignees),
    }


def diff_fields(spec: IssueSpec, remote: dict[str, Any]) -> list[str]:
    current = normalized_remote(remote)
    target = desired(spec)
    return [field for field in target if current[field] != target[field]]


def api_issue(repo: str, method: str, payload: dict[str, Any], number: int | None = None) -> dict[str, Any]:
    endpoint = f"repos/{repo}/issues" + (f"/{number}" if number is not None else "")
    return gh_json(
        ["gh", "api", endpoint, "--method", method, "--input", "-"],
        stdin=json.dumps(payload, ensure_ascii=False),
    )


def ensure_labels(repo: str, specs: list[IssueSpec]) -> None:
    existing = gh_json(["gh", "api", f"repos/{repo}/labels?per_page=100"])
    existing_names = {label["name"] for label in existing}
    requested = sorted({label for spec in specs for label in spec.labels})
    colors = {
        "bug": ("d73a4a", "Something is not working"),
        "enhancement": ("a2eeef", "New feature or improvement"),
        "tech-debt": ("6f42c1", "Technical debt and maintainability"),
        "testing": ("bfd4f2", "Testing and quality automation"),
        "evidence": ("0e8a16", "Evidence and provenance"),
        "domain-context": ("8250df", "Domain context management"),
        "priority:P0": ("b60205", "Critical priority"),
        "priority:P1": ("d93f0b", "High priority"),
        "priority:P2": ("fbca04", "Normal priority"),
        "area:backend": ("1d76db", "Backend"),
        "area:frontend": ("5319e7", "Frontend"),
        "area:fullstack": ("0052cc", "Full stack"),
    }
    for name in requested:
        if name in existing_names:
            continue
        color, description = colors.get(name, ("c5def5", "Managed by DataWeave issue manifest"))
        gh_json(
            ["gh", "api", f"repos/{repo}/labels", "--method", "POST", "--input", "-"],
            stdin=json.dumps({"name": name, "color": color, "description": description}),
        )
        print(f"  created label: {name}")


def sync_manifest(path: Path, repo: str, apply: bool, only: set[str]) -> None:
    require_tools()
    _, specs = load_manifest(path)
    selected = [spec for spec in specs if not only or spec.key in only]
    missing_keys = only - {spec.key for spec in specs}
    if missing_keys:
        fail(f"unknown issue keys: {', '.join(sorted(missing_keys))}")
    numberless = [spec for spec in selected if spec.number is None]
    remote_managed = get_remote_managed_issues(repo) if numberless else {}
    if apply:
        ensure_labels(repo, selected)
    changes = 0
    for spec in selected:
        if spec.number is None:
            recovered = remote_managed.get(spec.key)
            if recovered:
                number = int(recovered["number"])
                fields = diff_fields(spec, recovered)
                changes += 1
                suffix = f"; update: {', '.join(fields)}" if fields else ""
                print(f"RECOVER {spec.key} -> #{number}{suffix}")
                if apply:
                    update_number(path, spec.key, number)
                    if fields:
                        api_issue(repo, "PATCH", desired(spec), number)
                    print(f"  linked existing #{number}: {recovered['html_url']}")
                continue
            changes += 1
            print(f"CREATE {spec.key}: {spec.title}")
            if apply:
                try:
                    created = api_issue(
                        repo,
                        "POST",
                        {
                            "title": spec.title,
                            "body": spec.remote_body,
                            "labels": list(spec.labels),
                            "assignees": list(spec.assignees),
                        },
                    )
                except SystemExit:
                    print(
                        f"safe-stop: {spec.key} create result is unknown. "
                        "Do not create it manually; rerun sync --apply. "
                        "The next run will reconcile its stable key first.",
                        file=sys.stderr,
                    )
                    raise
                number = int(created["number"])
                update_number(path, spec.key, number)
                if spec.state == "closed":
                    api_issue(repo, "PATCH", {"state": "closed"}, number)
                print(f"  created #{number}: {created['html_url']}")
            continue
        remote = get_remote_issue(repo, spec.number)
        fields = diff_fields(spec, remote)
        if not fields:
            print(f"OK     {spec.key} -> #{spec.number}")
            continue
        changes += 1
        print(f"UPDATE {spec.key} -> #{spec.number}: {', '.join(fields)}")
        if apply:
            payload = desired(spec)
            api_issue(repo, "PATCH", payload, spec.number)
            print(f"  updated {remote['url']}")
    if apply:
        write_index(path, repo)
    mode = "applied" if apply else "planned"
    print(f"{mode}: {changes} change(s); {len(selected) - changes} unchanged")
    if changes and not apply:
        print("dry-run only; rerun with --apply to write GitHub issues")


def list_remote(repo: str, state: str) -> None:
    require_tools()
    issues = gh_json(
        [
            "gh", "issue", "list", "--repo", repo, "--limit", "1000", "--state", state,
            "--json", "number,title,state,labels,assignees,url,updatedAt",
        ]
    )
    if not issues:
        print("No GitHub issues found.")
        return
    for issue in issues:
        labels = ",".join(label["name"] for label in issue.get("labels", [])) or "-"
        print(f"#{issue['number']:<4} {issue['state']:<6} {issue['title']} [{labels}]")


def commit_for_issue(path: Path, keys: list[str], message: str, close: bool, add_all: bool, paths: list[str]) -> None:
    _, specs = load_manifest(path)
    by_key = {spec.key: spec for spec in specs}
    selected: list[IssueSpec] = []
    for key in keys:
        spec = by_key.get(key)
        if not spec:
            fail(f"unknown issue key: {key}")
        if spec.number is None:
            fail(f"{key} has no GitHub number; run sync --apply first")
        selected.append(spec)
    if add_all and paths:
        fail("use either --all or explicit paths, not both")
    if add_all:
        run(["git", "add", "-A"])
    elif paths:
        run(["git", "add", "--", *paths])
    staged = run(["git", "diff", "--cached", "--name-only"])
    if not staged:
        fail("no staged changes; pass --all, paths, or stage files first")
    keyword = "Closes" if close else "Refs"
    references = "\n".join(f"{keyword} #{spec.number}" for spec in selected)
    print("staged files:")
    print(staged)
    print(f"issue links:\n{references}")
    run(["git", "commit", "-m", message, "-m", references], capture=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage DataWeave GitHub issues from Markdown")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub owner/repo (default: {DEFAULT_REPO})")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Markdown issue manifest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="validate the Markdown manifest")
    check.set_defaults(action="check")

    index = subparsers.add_parser("index", help="regenerate the summary table")
    index.set_defaults(action="index")

    list_parser = subparsers.add_parser("list", help="list remote GitHub issues")
    list_parser.add_argument("--state", choices=("open", "closed", "all"), default="all")
    list_parser.set_defaults(action="list")

    sync = subparsers.add_parser("sync", help="create or update GitHub issues from Markdown")
    sync.add_argument("keys", nargs="*", help="optional issue keys; default syncs all")
    sync.add_argument("--apply", action="store_true", help="perform remote writes; default is dry-run")
    sync.set_defaults(action="sync")

    commit = subparsers.add_parser("commit", help="create a git commit linked to one or more issues")
    commit.add_argument("keys", nargs="+", help="issue keys such as DW-001")
    commit.add_argument("-m", "--message", required=True, help="git commit subject")
    commit.add_argument("--close", action="store_true", help="use Closes #N instead of Refs #N")
    commit.add_argument("--all", action="store_true", help="stage all changes before committing")
    commit.add_argument("--paths", nargs="+", default=[], help="files to stage; omit to use already staged files")
    commit.set_defaults(action="commit")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = args.manifest.resolve()
    if args.action == "check":
        _, specs = load_manifest(manifest)
        print(f"valid: {manifest} ({len(specs)} issues)")
    elif args.action == "index":
        write_index(manifest, args.repo)
    elif args.action == "list":
        list_remote(args.repo, args.state)
    elif args.action == "sync":
        sync_manifest(manifest, args.repo, args.apply, set(args.keys))
    elif args.action == "commit":
        commit_for_issue(manifest, args.keys, args.message, args.close, args.all, args.paths)


if __name__ == "__main__":
    main()
