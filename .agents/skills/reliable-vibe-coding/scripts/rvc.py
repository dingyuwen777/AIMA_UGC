#!/usr/bin/env python3
"""Reliable Vibe Coding 的项目发现缓存与并行变更检查工具。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from string import Template
from typing import Any, Iterable, Sequence


CONTEXT_SCHEMA = "rvc-project-context/v1"
CHANGE_SCHEMA = "rvc-change/v1"
GENERATOR_VERSION = "0.1.0"
STATE_DIRECTORY = ".reliable-vibe-coding"
CONTEXT_FILENAME = "project-context.json"
CHANGE_ID_PATTERN = re.compile(r"^CHG-\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*$")
CHANGE_STATUSES = {
    "approved",
    "blocked",
    "done",
    "in_progress",
    "proposed",
    "ready_for_review",
}
CHANGE_LIST_FIELDS = {
    "affected_areas",
    "affected_paths",
    "contracts",
    "data_changes",
    "depends_on",
}
CHANGE_SCALAR_FIELDS = {
    "branch",
    "created",
    "id",
    "level",
    "owner",
    "schema",
    "status",
    "title",
    "updated",
}
DOCUMENT_EXTENSIONS = {
    ".adoc",
    ".json",
    ".md",
    ".mdc",
    ".mdx",
    ".rst",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    STATE_DIRECTORY,
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "vendor",
    ".venv",
    "venv",
}
INSTRUCTION_NAMES = {
    "agents.md",
    "claude.md",
    "gemini.md",
    "copilot-instructions.md",
    ".cursorrules",
}
INSTRUCTION_DIRECTORIES = {
    ".claude/rules",
    ".cursor/rules",
    ".github/instructions",
    ".windsurf/rules",
}
MANIFEST_NAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    "requirements.txt",
    "pipfile",
    "pipfile.lock",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "gradle.properties",
    "composer.json",
    "composer.lock",
    "gemfile",
    "gemfile.lock",
    "mix.exs",
    "makefile",
    "justfile",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}
REQUIREMENT_TOKENS = {
    "acceptance",
    "backlog",
    "prd",
    "proposal",
    "requirement",
    "requirements",
    "rfc",
    "roadmap",
    "spec",
    "specification",
    "specifications",
    "stories",
}
REQUIREMENT_MARKERS = {
    "需求",
    "验收",
    "规格",
    "要件",
    "要求事項",
    "요구사항",
    "requisito",
    "requisitos",
    "exigence",
    "exigences",
    "anforderung",
    "anforderungen",
}
DOCUMENTATION_DIRECTORIES = {
    "adr",
    "architecture",
    "contracts",
    "decisions",
    "design",
    "docs",
    "documentation",
    "migrations",
    "product",
    "schemas",
    "specs",
}


def _run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _git_head(root: Path) -> str | None:
    result = _run_git(root, "rev-parse", "--verify", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def _is_git_repository(root: Path) -> bool:
    result = _run_git(root, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return False
    try:
        return Path(result.stdout.strip()).resolve() == root.resolve()
    except OSError:
        return False


def _normalise_relative_path(path: str | Path) -> str:
    value = str(path).replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def _is_safe_relative_path(path: str) -> bool:
    candidate = Path(path)
    return (
        bool(path)
        and not candidate.is_absolute()
        and ".." not in candidate.parts
        and not re.match(r"^[A-Za-z]:", path)
    )


def _safe_project_file(root: Path, relative_path: str) -> Path | None:
    """返回仓库内普通文件；拒绝符号链接和解析后逃逸的路径。"""
    if not _is_safe_relative_path(relative_path):
        return None
    candidate = root / relative_path
    try:
        if candidate.is_symlink():
            return None
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
        return candidate if resolved.is_file() else None
    except (OSError, RuntimeError, ValueError):
        return None


def _is_excluded(relative_path: str) -> bool:
    parts = [part.casefold() for part in Path(relative_path).parts]
    if any(part in EXCLUDED_DIRECTORIES for part in parts):
        return True
    return bool(parts and parts[0] == "changes")


def _classify_path(relative_path: str) -> str | None:
    relative = _normalise_relative_path(relative_path)
    if not relative or _is_excluded(relative):
        return None
    path = Path(relative)
    name = path.name.casefold()
    suffix = path.suffix.casefold()
    parts = [part.casefold() for part in path.parts]
    stem_tokens = {token for token in re.split(r"[^a-z0-9]+", path.stem.casefold()) if token}

    if name in INSTRUCTION_NAMES or relative.casefold() == ".github/copilot-instructions.md":
        return "instructions"
    if suffix in DOCUMENT_EXTENSIONS and any(
        relative.casefold().startswith(directory + "/")
        for directory in INSTRUCTION_DIRECTORIES
    ):
        return "instructions"
    if name in MANIFEST_NAMES:
        return "manifest"
    if suffix not in DOCUMENT_EXTENSIONS:
        return None
    if (
        stem_tokens & REQUIREMENT_TOKENS
        or set(parts) & REQUIREMENT_TOKENS
        or any(marker in relative.casefold() for marker in REQUIREMENT_MARKERS)
    ):
        return "requirements"
    if "contract" in stem_tokens or "contracts" in parts or "schemas" in parts:
        return "contract"
    if "migration" in stem_tokens or "migrations" in parts:
        return "migration"
    if set(parts[:-1]) & DOCUMENTATION_DIRECTORIES:
        return "documentation"
    if name.startswith("readme") or name in {
        "contributing.md",
        "security.md",
        "architecture.md",
        "design.md",
    }:
        return "documentation"
    return None


def _walk_files(root: Path) -> list[str]:
    files: list[str] = []
    for current_root, directory_names, file_names in os.walk(root):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name.casefold() not in EXCLUDED_DIRECTORIES and name.casefold() != "changes"
        )
        current_path = Path(current_root)
        for file_name in sorted(file_names):
            relative = _normalise_relative_path((current_path / file_name).relative_to(root))
            if not _is_excluded(relative):
                files.append(relative)
    return files


def _git_files(root: Path) -> list[str] | None:
    result = _run_git(root, "ls-files", "-co", "--exclude-standard", "-z")
    if result.returncode != 0:
        return None
    return sorted(
        {
            _normalise_relative_path(path)
            for path in result.stdout.split("\0")
            if path and not _is_excluded(path)
        }
    )


def _project_files(root: Path) -> list[str]:
    git_files = _git_files(root) if _is_git_repository(root) else None
    return git_files if git_files is not None else _walk_files(root)


def _candidate_paths(root: Path) -> list[str]:
    return sorted(
        path
        for path in _project_files(root)
        if _classify_path(path) and _safe_project_file(root, path) is not None
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _first_heading(path: Path) -> str | None:
    if path.suffix.casefold() not in {".md", ".mdx", ".rst", ".txt", ".adoc"}:
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            for _ in range(80):
                line = stream.readline()
                if not line:
                    break
                stripped = line.strip()
                if stripped.startswith("#"):
                    title = stripped.lstrip("#").strip()
                    return title or None
    except OSError:
        return None
    return None


def _read_package_scripts(path: Path) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    scripts = payload.get("scripts") if isinstance(payload, dict) else None
    if not isinstance(scripts, dict):
        return {}
    return {
        str(name): command
        for name, command in sorted(scripts.items())
        if isinstance(command, str)
    }


def _path_digest(paths: Iterable[str]) -> str:
    joined = "\0".join(sorted(paths)).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def _git_worktree_candidate_digest(
    root: Path, known_paths: Iterable[str] = ()
) -> str | None:
    result = _run_git(
        root,
        "-c",
        "core.quotepath=false",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    if result.returncode != 0:
        return None
    known = set(known_paths)
    entries: list[dict[str, Any]] = []
    records = result.stdout.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4:
            continue
        status = record[:2]
        paths = [record[3:]]
        if ("R" in status or "C" in status) and index < len(records):
            paths.append(records[index])
            index += 1
        for path in paths:
            relative = _normalise_relative_path(path)
            if not _is_safe_relative_path(relative):
                continue
            if _classify_path(relative) is None and relative not in known:
                continue
            candidate = root / relative
            if candidate.exists() or candidate.is_symlink():
                absolute = _safe_project_file(root, relative)
                if absolute is None:
                    continue
            else:
                absolute = None
            entries.append(
                {
                    "path": relative,
                    "status": status,
                    "sha256": _sha256(absolute) if absolute is not None else None,
                }
            )
    encoded = json.dumps(
        sorted(entries, key=lambda item: (item["path"], item["status"])),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def scan_project(root: str | Path) -> dict[str, Any]:
    """完整扫描项目中的高价值事实入口并返回可移植索引。"""
    project_root = Path(root).resolve()
    candidates = _candidate_paths(project_root)
    documents: list[dict[str, Any]] = []
    package_scripts: dict[str, dict[str, str]] = {}

    for relative in candidates:
        absolute = _safe_project_file(project_root, relative)
        if absolute is None:
            continue
        kind = _classify_path(relative)
        if kind is None:
            continue
        item: dict[str, Any] = {
            "path": relative,
            "kind": kind,
            "size": absolute.stat().st_size,
            "sha256": _sha256(absolute),
        }
        title = _first_heading(absolute)
        if title:
            item["title"] = title
        documents.append(item)
        if Path(relative).name.casefold() == "package.json":
            package_scripts[relative] = _read_package_scripts(absolute)

    directories: dict[str, dict[str, Any]] = {}
    for document in documents:
        parent = _normalise_relative_path(Path(document["path"]).parent)
        if parent == ".":
            parent = ""
        entry = directories.setdefault(parent, {"path": parent, "kinds": set(), "count": 0})
        entry["kinds"].add(document["kind"])
        entry["count"] += 1

    directory_list = [
        {"path": value["path"], "kinds": sorted(value["kinds"]), "count": value["count"]}
        for _, value in sorted(directories.items())
    ]
    git_repository = _is_git_repository(project_root)
    known_paths = [item["path"] for item in documents]
    return {
        "schema": CONTEXT_SCHEMA,
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git": {
            "repository": git_repository,
            "indexed_at_commit": _git_head(project_root) if git_repository else None,
            "worktree_candidate_digest": (
                _git_worktree_candidate_digest(project_root, known_paths)
                if git_repository
                else None
            ),
        },
        "candidate_path_digest": _path_digest(item["path"] for item in documents),
        "documents": sorted(documents, key=lambda item: item["path"]),
        "directories": directory_list,
        "package_scripts": package_scripts,
    }


def _context_path(root: Path) -> Path:
    return root / STATE_DIRECTORY / CONTEXT_FILENAME


def _write_context(root: Path, context: dict[str, Any]) -> None:
    state_directory = root / STATE_DIRECTORY
    state_directory.mkdir(parents=True, exist_ok=True)
    target = state_directory / CONTEXT_FILENAME
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=state_directory,
        prefix="project-context.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        json.dump(context, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, target)


def _load_context(root: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(_context_path(root).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _git_candidate_changes(root: Path, context: dict[str, Any]) -> bool | None:
    git_context = context.get("git")
    if not isinstance(git_context, dict) or not git_context.get("repository"):
        return None
    if not _is_git_repository(root):
        return None
    indexed_head = git_context.get("indexed_at_commit")
    current_head = _git_head(root)
    if not isinstance(indexed_head, str) or not current_head:
        return None

    known_paths = {
        item.get("path")
        for item in context.get("documents", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    if any(not _is_safe_relative_path(path) for path in known_paths):
        return True
    current_worktree_digest = _git_worktree_candidate_digest(root, known_paths)
    indexed_worktree_digest = git_context.get("worktree_candidate_digest")
    if current_worktree_digest is None or not isinstance(indexed_worktree_digest, str):
        return None
    if current_worktree_digest != indexed_worktree_digest:
        return True

    ancestor = _run_git(root, "merge-base", "--is-ancestor", indexed_head, current_head)
    if ancestor.returncode != 0:
        return True

    changed: set[str] = set()
    if indexed_head != current_head:
        result = _run_git(
            root,
            "-c",
            "core.quotepath=false",
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
            "--diff-filter=ACDMRTUXB",
            indexed_head,
            current_head,
        )
        if result.returncode != 0:
            return None
        changed.update(
            _normalise_relative_path(path)
            for path in result.stdout.split("\0")
            if path
        )

    return any(_classify_path(path) is not None or path in known_paths for path in changed)


def _context_is_fresh(root: Path, context: dict[str, Any]) -> bool:
    if context.get("schema") != CONTEXT_SCHEMA:
        return False
    git_changes = _git_candidate_changes(root, context)
    if git_changes is not None:
        return not git_changes

    documents = context.get("documents")
    if not isinstance(documents, list):
        return False
    current_candidates = _candidate_paths(root)
    if _path_digest(current_candidates) != context.get("candidate_path_digest"):
        return False
    for item in documents:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            return False
        if not _is_safe_relative_path(item["path"]):
            return False
        path = _safe_project_file(root, item["path"])
        try:
            if path is None or path.stat().st_size != item.get("size"):
                return False
            if _sha256(path) != item.get("sha256"):
                return False
        except OSError:
            return False
    return True


def ensure_project_context(
    root: str | Path, *, force: bool = False
) -> tuple[dict[str, Any], str]:
    """创建或按需刷新项目索引，返回索引和本次模式。"""
    project_root = Path(root).resolve()
    if not project_root.is_dir():
        raise NotADirectoryError(project_root)
    existing = _load_context(project_root)
    if existing is not None and not force and _context_is_fresh(project_root, existing):
        return existing, "cache_hit"
    context = scan_project(project_root)
    _write_context(project_root, context)
    return context, "refreshed" if existing is not None else "created"


def _validate_change_id(change_id: str) -> None:
    if not CHANGE_ID_PATTERN.fullmatch(change_id):
        raise ValueError(
            "change id 必须使用 CHG-YYYYMMDD-kebab-case 格式，例如 "
            "CHG-20260813-report-export"
        )


def _yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _yaml_list(name: str, values: Sequence[str]) -> list[str]:
    if not values:
        return [f"{name}: []"]
    return [f"{name}:", *(f"  - {_yaml_scalar(value)}" for value in values)]


def create_change(
    root: str | Path,
    *,
    change_id: str,
    title: str,
    owner: str,
    branch: str,
    level: str,
    affected_areas: Sequence[str] = (),
    affected_paths: Sequence[str] = (),
    contracts: Sequence[str] = (),
    data_changes: Sequence[str] = (),
    depends_on: Sequence[str] = (),
) -> Path:
    """以独占目录创建一个可由 Git 追踪的 CHANGE.md。"""
    _validate_change_id(change_id)
    normalised_level = level.upper()
    if normalised_level not in {"L2", "L3"}:
        raise ValueError("只有需要追踪的 L2 或 L3 任务可以创建 CHANGE.md")
    project_root = Path(root).resolve()
    today = datetime.now(timezone.utc).date().isoformat()
    metadata = {
        "schema": CHANGE_SCHEMA,
        "id": change_id,
        "title": title,
        "level": normalised_level,
        "status": "proposed",
        "owner": owner,
        "branch": branch,
        "created": today,
        "updated": today,
        "depends_on": list(depends_on),
        "affected_areas": list(affected_areas),
        "affected_paths": list(affected_paths),
        "contracts": list(contracts),
        "data_changes": list(data_changes),
    }
    _validate_change_metadata(metadata)
    template_path = Path(__file__).resolve().parents[1] / "assets" / "CHANGE.template.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    content = template.substitute(
        change_id=_yaml_scalar(change_id),
        title=_yaml_scalar(title),
        level=normalised_level,
        owner=_yaml_scalar(owner),
        branch=_yaml_scalar(branch),
        created=today,
        updated=today,
        depends_on="\n".join(_yaml_list("depends_on", metadata["depends_on"])),
        affected_areas="\n".join(
            _yaml_list("affected_areas", metadata["affected_areas"])
        ),
        affected_paths="\n".join(
            _yaml_list("affected_paths", metadata["affected_paths"])
        ),
        contracts="\n".join(_yaml_list("contracts", metadata["contracts"])),
        data_changes="\n".join(
            _yaml_list("data_changes", metadata["data_changes"])
        ),
    )
    active_directory = project_root / "changes" / "active"
    active_directory.mkdir(parents=True, exist_ok=True)
    change_directory = active_directory / change_id
    change_directory.mkdir(exist_ok=False)
    change_path = change_directory / "CHANGE.md"
    try:
        with change_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            if not content.endswith("\n"):
                stream.write("\n")
    except OSError:
        change_directory.rmdir()
        raise
    return change_path


def _parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped == "[]":
        return []
    if stripped.startswith(('"', "'")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return stripped.strip('"\'')
    return stripped


def _validate_change_metadata(
    metadata: dict[str, Any], source: Path | None = None
) -> None:
    missing = sorted((CHANGE_SCALAR_FIELDS | CHANGE_LIST_FIELDS) - set(metadata))
    if missing:
        raise ValueError(f"Change frontmatter 缺少字段：{', '.join(missing)}")
    for field in CHANGE_SCALAR_FIELDS:
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Change 字段 {field} 必须是非空字符串")
    if metadata["schema"] != CHANGE_SCHEMA:
        raise ValueError(f"不支持的 Change schema：{metadata['schema']}")
    _validate_change_id(metadata["id"])
    if metadata["level"].upper() not in {"L2", "L3"}:
        raise ValueError("Change level 必须是 L2 或 L3")
    if metadata["status"].casefold() not in CHANGE_STATUSES:
        raise ValueError(f"不支持的 Change status：{metadata['status']}")
    for field in CHANGE_LIST_FIELDS:
        values = metadata.get(field)
        if not isinstance(values, list):
            raise ValueError(f"Change 字段 {field} 必须是字符串列表")
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError(f"Change 字段 {field} 不能包含空值或非字符串")
    for path in metadata["affected_paths"]:
        normalised = _normalise_relative_path(path)
        if not _is_safe_relative_path(normalised):
            raise ValueError(f"Change 字段 affected_paths 包含不安全路径：{path}")
    for dependency in metadata["depends_on"]:
        if not CHANGE_ID_PATTERN.fullmatch(dependency):
            raise ValueError(f"Change 字段 depends_on 包含非法 ID：{dependency}")
    if source is not None and source.name.casefold() == "change.md":
        if source.parent.name != metadata["id"]:
            raise ValueError(
                f"Change id {metadata['id']} 与目录 {source.parent.name} 不一致"
            )


def read_change_metadata(path: str | Path) -> dict[str, Any]:
    """读取 CHANGE.md 中受支持的扁平 YAML frontmatter。"""
    source = Path(path)
    lines = source.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} 缺少 frontmatter")
    metadata: dict[str, Any] = {}
    current_list: str | None = None
    for line in lines[1:]:
        if line.strip() == "---":
            _validate_change_metadata(metadata, source)
            return metadata
        if line.startswith("  - ") and current_list:
            metadata[current_list].append(_parse_scalar(line[4:]))
            continue
        current_list = None
        if ":" not in line:
            if line.strip() and not line.lstrip().startswith("#"):
                raise ValueError(f"{path} 含无法解析的 frontmatter 行：{line}")
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key in metadata:
            raise ValueError(f"{path} 的 frontmatter 字段重复：{key}")
        value = raw_value.strip()
        if not value:
            metadata[key] = []
            current_list = key
        else:
            metadata[key] = _parse_scalar(value)
    raise ValueError(f"{path} 的 frontmatter 未闭合")


def _active_changes(root: Path) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for path in sorted((root / "changes" / "active").glob("*/CHANGE.md")):
        metadata = read_change_metadata(path)
        metadata["_path"] = _normalise_relative_path(path.relative_to(root))
        if str(metadata.get("status", "")).casefold() not in {"archived", "cancelled", "done"}:
            changes.append(metadata)
    return changes


def _normalised_values(metadata: dict[str, Any], key: str) -> list[str]:
    value = metadata.get(key, [])
    if not isinstance(value, list):
        return []
    return sorted({str(item).strip().casefold() for item in value if str(item).strip()})


def _path_overlap(left: str, right: str) -> bool:
    left_path = left.replace("\\", "/").strip("/").casefold()
    right_path = right.replace("\\", "/").strip("/").casefold()
    left_path = "" if left_path == "." else left_path
    right_path = "" if right_path == "." else right_path
    if not left_path or not right_path:
        return True
    return (
        left_path == right_path
        or left_path.startswith(right_path + "/")
        or right_path.startswith(left_path + "/")
    )


def detect_conflicts(root: str | Path) -> list[dict[str, Any]]:
    """检测进行中变更在路径、Contract 和数据上的显式重叠。"""
    project_root = Path(root).resolve()
    conflicts: list[dict[str, Any]] = []
    for left, right in itertools.combinations(_active_changes(project_root), 2):
        overlaps: dict[str, list[Any]] = {}
        for key in ("affected_areas", "contracts", "data_changes"):
            shared = sorted(set(_normalised_values(left, key)) & set(_normalised_values(right, key)))
            if shared:
                overlaps[key] = shared
        path_pairs = sorted(
            {
                (left_path, right_path)
                for left_path in _normalised_values(left, "affected_paths")
                for right_path in _normalised_values(right, "affected_paths")
                if _path_overlap(left_path, right_path)
            }
        )
        if path_pairs:
            overlaps["affected_paths"] = [list(pair) for pair in path_pairs]
        if not overlaps:
            continue
        severity = (
            "high"
            if "contracts" in overlaps
            or "data_changes" in overlaps
            or str(left.get("level", "")).upper() == "L3"
            or str(right.get("level", "")).upper() == "L3"
            else "medium"
        )
        conflicts.append(
            {
                "left": left.get("id"),
                "right": right.get("id"),
                "severity": severity,
                "overlaps": overlaps,
            }
        )
    return conflicts


def _json_print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="发现项目事实入口，并检查并行 Change 的显式冲突。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover", help="创建或刷新项目发现缓存")
    discover.add_argument("--root", default=".")
    discover.add_argument("--force", action="store_true")
    discover.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="列出进行中 Change 和冲突")
    status.add_argument("--root", default=".")
    status.add_argument("--json", action="store_true")

    new_change = subparsers.add_parser("new-change", help="原子创建一个 L2/L3 Change")
    new_change.add_argument("--root", default=".")
    new_change.add_argument("--id", required=True, dest="change_id")
    new_change.add_argument("--title", required=True)
    new_change.add_argument("--owner", required=True)
    new_change.add_argument("--branch", required=True)
    new_change.add_argument("--level", choices=("L2", "L3"), required=True)
    new_change.add_argument("--area", action="append", default=[])
    new_change.add_argument("--path", action="append", default=[])
    new_change.add_argument("--contract", action="append", default=[])
    new_change.add_argument("--data-change", action="append", default=[])
    new_change.add_argument("--depends-on", action="append", default=[])

    conflicts = subparsers.add_parser("conflicts", help="检查进行中 Change 的重叠")
    conflicts.add_argument("--root", default=".")
    conflicts.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行命令行入口。"""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    root = Path(arguments.root).resolve()
    try:
        if arguments.command == "discover":
            context, mode = ensure_project_context(root, force=arguments.force)
            if arguments.json:
                _json_print({"mode": mode, "context": context})
            else:
                print(f"{mode}: {len(context['documents'])} 个事实入口")
            return 0
        if arguments.command == "new-change":
            path = create_change(
                root,
                change_id=arguments.change_id,
                title=arguments.title,
                owner=arguments.owner,
                branch=arguments.branch,
                level=arguments.level,
                affected_areas=arguments.area,
                affected_paths=arguments.path,
                contracts=arguments.contract,
                data_changes=arguments.data_change,
                depends_on=arguments.depends_on,
            )
            print(_normalise_relative_path(path.relative_to(root)))
            return 0
        changes = _active_changes(root)
        conflicts = detect_conflicts(root)
        if arguments.command == "conflicts":
            if arguments.json:
                _json_print(conflicts)
            elif not conflicts:
                print("未发现显式重叠。")
            else:
                for conflict in conflicts:
                    print(
                        f"[{conflict['severity']}] {conflict['left']} <-> "
                        f"{conflict['right']}: {', '.join(conflict['overlaps'])}"
                    )
            return 2 if conflicts else 0
        payload = {"changes": changes, "conflicts": conflicts}
        if arguments.json:
            _json_print(payload)
        else:
            print(f"进行中 Change: {len(changes)}；显式冲突: {len(conflicts)}")
        return 2 if conflicts else 0
    except (FileExistsError, NotADirectoryError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
