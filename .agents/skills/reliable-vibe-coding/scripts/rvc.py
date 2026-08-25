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
    # JavaScript / TypeScript
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "deno.json",
    "deno.jsonc",
    "deno.lock",
    # Python
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    "requirements.txt",
    "pipfile",
    "pipfile.lock",
    # Rust
    "cargo.toml",
    "cargo.lock",
    # Go
    "go.mod",
    "go.sum",
    "go.work",
    "go.work.sum",
    # Java / Kotlin
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
    "libs.versions.toml",
    # .NET
    "global.json",
    "directory.build.props",
    "directory.build.targets",
    "directory.packages.props",
    "nuget.config",
    "packages.lock.json",
    # C / C++
    "cmakelists.txt",
    "cmakepresets.json",
    "meson.build",
    "meson_options.txt",
    "conanfile.py",
    "conanfile.txt",
    "vcpkg.json",
    "vcpkg-configuration.json",
    # Swift / Apple
    "package.swift",
    "package.resolved",
    "project.pbxproj",
    "contents.xcworkspacedata",
    # Dart / Flutter
    "pubspec.yaml",
    "pubspec.lock",
    "melos.yaml",
    # PHP
    "composer.json",
    "composer.lock",
    # Ruby
    "gemfile",
    "gemfile.lock",
    # Elixir
    "mix.exs",
    "mix.lock",
    # Additional build / package systems
    "build.zig",
    "build.zig.zon",
    "makefile",
    "justfile",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}
MANIFEST_SUFFIXES = {
    ".csproj",
    ".fsproj",
    ".vbproj",
    ".sln",
    ".slnx",
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
    if name in MANIFEST_NAMES or suffix in MANIFEST_SUFFIXES:
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
    try:
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _load_context(root: Path) -> dict[str, Any] | None:
    target = _context_path(root)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _validate_context(context: dict[str, Any]) -> bool:
    return context.get("schema") == CONTEXT_SCHEMA and context.get("generator_version") == GENERATOR_VERSION


def _context_stale(root: Path, context: dict[str, Any]) -> bool:
    if not _validate_context(context):
        return True
    documents = context.get("documents")
    if not isinstance(documents, list):
        return True
    known: dict[str, str] = {}
    for item in documents:
        if not isinstance(item, dict):
            return True
        path = item.get("path")
        sha256 = item.get("sha256")
        if not isinstance(path, str) or not isinstance(sha256, str):
            return True
        known[path] = sha256

    candidates = _candidate_paths(root)
    if _path_digest(candidates) != context.get("candidate_path_digest"):
        return True

    git = context.get("git")
    if not isinstance(git, dict):
        return True
    git_repository = _is_git_repository(root)
    if bool(git.get("repository")) != git_repository:
        return True
    if git_repository:
        indexed_commit = git.get("indexed_at_commit")
        current_head = _git_head(root)
        if indexed_commit != current_head:
            if not isinstance(indexed_commit, str) or not isinstance(current_head, str):
                return True
            ancestor = _run_git(root, "merge-base", "--is-ancestor", indexed_commit, current_head)
            if ancestor.returncode != 0:
                return True
        expected_digest = _git_worktree_candidate_digest(root, known)
        if expected_digest != git.get("worktree_candidate_digest"):
            return True

    for relative, expected_sha in known.items():
        path = _safe_project_file(root, relative)
        if path is None or _sha256(path) != expected_sha:
            return True
    return False


def discover_project(root: str | Path) -> tuple[str, dict[str, Any]]:
    project_root = Path(root).resolve()
    cached = _load_context(project_root)
    if cached is not None and not _context_stale(project_root, cached):
        return "cache_hit", cached
    context = scan_project(project_root)
    _write_context(project_root, context)
    return ("refreshed" if cached is not None else "created"), context


def _parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    _, frontmatter, body = text.split("---\n", 2)
    data: dict[str, Any] = {}
    current_list: str | None = None
    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith("  - "):
            if current_list is None:
                raise ValueError(f"{path}: list item without a key")
            data[current_list].append(line[4:].strip())
            continue
        if ":" not in line:
            raise ValueError(f"{path}: invalid frontmatter line: {line}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        current_list = None
        if raw_value == "[]":
            data[key] = []
        elif raw_value:
            data[key] = raw_value.strip('"\'')
        else:
            data[key] = []
            current_list = key
    return data, body


def _validate_change(change: dict[str, Any], path: Path) -> None:
    if change.get("schema") != CHANGE_SCHEMA:
        raise ValueError(f"{path}: unsupported schema {change.get('schema')!r}")
    for field in CHANGE_SCALAR_FIELDS:
        value = change.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{path}: missing scalar field {field}")
    if not CHANGE_ID_PATTERN.match(change["id"]):
        raise ValueError(f"{path}: invalid change id {change['id']!r}")
    if change["status"] not in CHANGE_STATUSES:
        raise ValueError(f"{path}: invalid change status {change['status']!r}")
    if change["level"] not in {"L2", "L3"}:
        raise ValueError(f"{path}: invalid change level {change['level']!r}")
    for field in CHANGE_LIST_FIELDS:
        value = change.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{path}: field {field} must be a list of strings")
    for field in {"affected_paths"}:
        for value in change[field]:
            if not _is_safe_relative_path(value):
                raise ValueError(f"{path}: unsafe relative path {value!r}")
    for dependency in change["depends_on"]:
        if not CHANGE_ID_PATTERN.match(dependency):
            raise ValueError(f"{path}: invalid dependency {dependency!r}")


def _active_change_paths(root: Path) -> list[Path]:
    active = root / "changes" / "active"
    if not active.exists():
        return []
    return sorted(path for path in active.glob("*/CHANGE.md") if path.is_file())


def _load_change(path: Path) -> dict[str, Any]:
    change, body = _parse_frontmatter(path)
    _validate_change(change, path)
    change["_path"] = _normalise_relative_path(path)
    change["_body"] = body
    return change


def active_changes(root: str | Path) -> list[dict[str, Any]]:
    project_root = Path(root).resolve()
    changes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in _active_change_paths(project_root):
        change = _load_change(path)
        if change["id"] in seen_ids:
            raise ValueError(f"duplicate change id: {change['id']}")
        seen_ids.add(change["id"])
        changes.append(change)
    return changes


def _path_overlap(first: str, second: str) -> bool:
    first_path = Path(first)
    second_path = Path(second)
    return first_path == second_path or first_path in second_path.parents or second_path in first_path.parents


def _change_overlap(first: dict[str, Any], second: dict[str, Any]) -> dict[str, list[str]]:
    overlap: dict[str, list[str]] = {}
    for field in ("affected_areas", "contracts", "data_changes"):
        shared = sorted(set(first[field]) & set(second[field]))
        if shared:
            overlap[field] = shared
    shared_paths = sorted(
        {
            f"{left} <-> {right}"
            for left in first["affected_paths"]
            for right in second["affected_paths"]
            if _path_overlap(left, right)
        }
    )
    if shared_paths:
        overlap["affected_paths"] = shared_paths
    dependencies = []
    if second["id"] in first["depends_on"]:
        dependencies.append(f"{first['id']} depends on {second['id']}")
    if first["id"] in second["depends_on"]:
        dependencies.append(f"{second['id']} depends on {first['id']}")
    if dependencies:
        overlap["depends_on"] = dependencies
    return overlap


def find_conflicts(root: str | Path) -> list[dict[str, Any]]:
    changes = active_changes(root)
    conflicts: list[dict[str, Any]] = []
    for first, second in itertools.combinations(changes, 2):
        overlap = _change_overlap(first, second)
        if overlap:
            conflicts.append(
                {
                    "changes": [first["id"], second["id"]],
                    "overlap": overlap,
                }
            )
    return conflicts


def _yaml_scalar(key: str, value: str) -> str:
    if key in {"created", "updated"}:
        return value
    return json.dumps(value, ensure_ascii=False)


def _list_frontmatter(key: str, values: Sequence[str]) -> str:
    if not values:
        return f"{key}: []"
    return f"{key}:\n" + "\n".join(f"  - {_yaml_scalar(key, value)}" for value in values)


def _load_change_template() -> Template:
    path = Path(__file__).resolve().parent.parent / "assets" / "CHANGE.template.md"
    return Template(path.read_text(encoding="utf-8"))


def _ensure_new_change_metadata(
    *,
    change_id: str,
    title: str,
    owner: str,
    branch: str,
    level: str,
    affected_areas: Sequence[str],
    affected_paths: Sequence[str],
    contracts: Sequence[str],
    data_changes: Sequence[str],
    depends_on: Sequence[str],
) -> dict[str, Any]:
    candidate = {
        "schema": CHANGE_SCHEMA,
        "id": change_id,
        "title": title,
        "level": level,
        "status": "proposed",
        "owner": owner,
        "branch": branch,
        "created": datetime.now(timezone.utc).date().isoformat(),
        "updated": datetime.now(timezone.utc).date().isoformat(),
        "depends_on": list(depends_on),
        "affected_areas": list(affected_areas),
        "affected_paths": list(affected_paths),
        "contracts": list(contracts),
        "data_changes": list(data_changes),
    }
    _validate_change(candidate, Path("<new-change>"))
    return candidate


def create_change(
    root: str | Path,
    *,
    change_id: str,
    title: str,
    owner: str,
    branch: str,
    level: str,
    affected_areas: Sequence[str],
    affected_paths: Sequence[str],
    contracts: Sequence[str] = (),
    data_changes: Sequence[str] = (),
    depends_on: Sequence[str] = (),
) -> Path:
    project_root = Path(root).resolve()
    change = _ensure_new_change_metadata(
        change_id=change_id,
        title=title,
        owner=owner,
        branch=branch,
        level=level,
        affected_areas=affected_areas,
        affected_paths=affected_paths,
        contracts=contracts,
        data_changes=data_changes,
        depends_on=depends_on,
    )
    target_directory = project_root / "changes" / "active" / change_id
    target = target_directory / "CHANGE.md"
    if target.exists():
        raise FileExistsError(f"change already exists: {target}")
    target_directory.mkdir(parents=True, exist_ok=False)
    template = _load_change_template()
    body = template.substitute(
        change_id=_yaml_scalar("id", change["id"]),
        title=_yaml_scalar("title", change["title"]),
        level=_yaml_scalar("level", change["level"]),
        owner=_yaml_scalar("owner", change["owner"]),
        branch=_yaml_scalar("branch", change["branch"]),
        created=_yaml_scalar("created", change["created"]),
        updated=_yaml_scalar("updated", change["updated"]),
        depends_on=_list_frontmatter("depends_on", change["depends_on"]),
        affected_areas=_list_frontmatter("affected_areas", change["affected_areas"]),
        affected_paths=_list_frontmatter("affected_paths", change["affected_paths"]),
        contracts=_list_frontmatter("contracts", change["contracts"]),
        data_changes=_list_frontmatter("data_changes", change["data_changes"]),
    )
    target.write_text(body, encoding="utf-8")
    return target


def _json_dump(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _command_discover(arguments: argparse.Namespace) -> int:
    status, context = discover_project(arguments.root)
    payload = {"status": status, "context": context}
    if arguments.json:
        _json_dump(payload)
    else:
        print(f"{status}: {_context_path(Path(arguments.root).resolve())}")
    return 0


def _command_status(arguments: argparse.Namespace) -> int:
    changes = active_changes(arguments.root)
    conflicts = find_conflicts(arguments.root)
    payload = {"changes": changes, "conflicts": conflicts}
    if arguments.json:
        _json_dump(payload)
    else:
        for change in changes:
            print(f"{change['id']} [{change['level']}/{change['status']}] owner={change['owner']} branch={change['branch']}")
        if conflicts:
            print(f"conflicts: {len(conflicts)}")
    return 0


def _command_conflicts(arguments: argparse.Namespace) -> int:
    conflicts = find_conflicts(arguments.root)
    if arguments.json:
        _json_dump(conflicts)
    else:
        if conflicts:
            for conflict in conflicts:
                print(f"{conflict['changes'][0]} <-> {conflict['changes'][1]}: {conflict['overlap']}")
        else:
            print("no explicit conflicts found")
    return 2 if conflicts else 0


def _command_new_change(arguments: argparse.Namespace) -> int:
    target = create_change(
        arguments.root,
        change_id=arguments.id,
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
    print(target)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover", help="创建或刷新项目导航缓存")
    discover.add_argument("--root", default=".")
    discover.add_argument("--json", action="store_true")
    discover.set_defaults(handler=_command_discover)

    status = subparsers.add_parser("status", help="显示当前 Active Change 和显式冲突")
    status.add_argument("--root", default=".")
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=_command_status)

    conflicts = subparsers.add_parser("conflicts", help="检查 Active Change 的显式冲突")
    conflicts.add_argument("--root", default=".")
    conflicts.add_argument("--json", action="store_true")
    conflicts.set_defaults(handler=_command_conflicts)

    new_change = subparsers.add_parser("new-change", help="创建单文件 Active Change")
    new_change.add_argument("--root", default=".")
    new_change.add_argument("--id", required=True)
    new_change.add_argument("--title", required=True)
    new_change.add_argument("--owner", required=True)
    new_change.add_argument("--branch", required=True)
    new_change.add_argument("--level", choices=["L2", "L3"], required=True)
    new_change.add_argument("--area", action="append", default=[])
    new_change.add_argument("--path", action="append", default=[])
    new_change.add_argument("--contract", action="append", default=[])
    new_change.add_argument("--data-change", action="append", default=[])
    new_change.add_argument("--depends-on", action="append", default=[])
    new_change.set_defaults(handler=_command_new_change)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    return int(arguments.handler(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
