#!/usr/bin/env python3
"""Coding Skill 的项目发现缓存、目标项目 Bootstrap 与并行变更检查工具。"""

from __future__ import annotations

import argparse
from datetime import datetime
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
from zoneinfo import ZoneInfo


CONTEXT_SCHEMA = "coding-project-context/v1"
CHANGE_SCHEMA = "coding-change/v1"
GENERATOR_VERSION = "0.4.0"
CONTEXT_DIRECTORY = ".agents"
CONTEXT_FILENAME = "project-context.json"
DEFAULT_CHANGE_DIRECTORY = Path(".agents") / "changes"
TOP_LEVEL_CHANGE_DIRECTORY = Path("changes")
BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")
AGENTS_FILENAME = "AGENTS.md"
GITIGNORE_FILENAME = ".gitignore"
AGENTS_MANAGED_START = "<!-- agent-skills:managed:start -->"
AGENTS_MANAGED_END = "<!-- agent-skills:managed:end -->"
CACHE_IGNORE_RULE = ".agents/project-context.json"
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
    "completion_gate",
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


def _beijing_now() -> datetime:
    """返回带明确 Asia/Shanghai 时区信息的当前北京时间。"""
    return datetime.now(BEIJING_TIMEZONE)


def _run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """在目标仓库内运行只读 Git 命令并返回完整结果。"""
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _git_head(root: Path) -> str | None:
    """返回当前 HEAD；不是 Git 仓库或无 HEAD 时返回空值。"""
    result = _run_git(root, "rev-parse", "--verify", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def _is_git_repository(root: Path) -> bool:
    """判断给定目录本身是否为当前 Git 仓库根。"""
    result = _run_git(root, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return False
    try:
        return Path(result.stdout.strip()).resolve() == root.resolve()
    except OSError:
        return False


def _normalise_relative_path(path: str | Path) -> str:
    """把路径规范成仓库相对的正斜杠形式。"""
    value = str(path).replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def _is_safe_relative_path(path: str) -> bool:
    """判断字符串是否为不逃逸仓库的安全相对路径。"""
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


def _is_change_management_path(relative_path: str) -> bool:
    """只排除 Coding 自有 `.agents/changes`，避免把项目其他 `changes` 治理从事实发现中隐藏。"""
    parts = [part.casefold() for part in Path(relative_path).parts]
    return len(parts) >= 2 and parts[0] == ".agents" and parts[1] == "changes"


def _is_excluded(relative_path: str) -> bool:
    """判断项目发现是否应跳过该路径。"""
    parts = [part.casefold() for part in Path(relative_path).parts]
    if any(part in EXCLUDED_DIRECTORIES for part in parts):
        return True
    return _is_change_management_path(relative_path)


def _classify_path(relative_path: str) -> str | None:
    """按文件名和路径把候选事实入口分类。"""
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
    """在非 Git 仓库中有界遍历可见项目文件。"""
    files: list[str] = []
    for current_root, directory_names, file_names in os.walk(root):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name.casefold() not in EXCLUDED_DIRECTORIES
        )
        current_path = Path(current_root)
        for file_name in sorted(file_names):
            relative = _normalise_relative_path((current_path / file_name).relative_to(root))
            if not _is_excluded(relative):
                files.append(relative)
    return files


def _git_files(root: Path) -> list[str] | None:
    """返回 Git 已跟踪与未忽略未跟踪文件；Git 不可用时返回空值。"""
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
    """优先用 Git 枚举项目文件，必要时退化为文件系统遍历。"""
    git_files = _git_files(root) if _is_git_repository(root) else None
    return git_files if git_files is not None else _walk_files(root)


def _candidate_paths(root: Path) -> list[str]:
    """返回当前仓库可安全读取的高价值事实候选路径。"""
    return sorted(
        path
        for path in _project_files(root)
        if _classify_path(path) and _safe_project_file(root, path) is not None
    )


def _sha256(path: Path) -> str:
    """计算文件 SHA-256，作为轻量失效指纹。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _first_heading(path: Path) -> str | None:
    """从文本型文档前部读取第一个 Markdown 风格标题。"""
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
    """只提取 package.json 中真实存在的字符串 scripts。"""
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
    """对候选路径集合生成稳定摘要。"""
    joined = "\0".join(sorted(paths)).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def _git_worktree_candidate_digest(
    root: Path, known_paths: Iterable[str] = ()
) -> str | None:
    """只对事实候选相关工作区变化计算摘要，避免普通源码变化无意义刷新缓存。"""
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
        "generated_at": _beijing_now().replace(microsecond=0).isoformat(),
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
    """返回项目固定的 Coding 本地缓存文件路径。"""
    return root / CONTEXT_DIRECTORY / CONTEXT_FILENAME


def _write_context(root: Path, context: dict[str, Any]) -> None:
    """把本地项目索引原子写入项目根目录下的 .agents 缓存文件。"""
    target = _context_path(root)
    state_directory = target.parent
    state_directory.mkdir(parents=True, exist_ok=True)
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
    """只读取 .agents/project-context.json；损坏或不存在时返回空值。"""
    try:
        payload = json.loads(_context_path(root).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _git_candidate_changes(root: Path, context: dict[str, Any]) -> bool | None:
    """判断索引基线之后是否出现需要刷新缓存的 Git 候选事实变化。"""
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
    """根据 schema、Git 基线和候选文件指纹判断缓存是否仍可复用。"""
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
    """创建或按需刷新本地项目索引，返回索引和本次模式。"""
    project_root = Path(root).resolve()
    if not project_root.is_dir():
        raise NotADirectoryError(project_root)
    existing = _load_context(project_root)
    if existing is not None and not force and _context_is_fresh(project_root, existing):
        return existing, "cache_hit"
    context = scan_project(project_root)
    _write_context(project_root, context)
    return context, "refreshed" if existing is not None else "created"


def _asset_text(name: str) -> str:
    """读取 Coding Skill 自带 UTF-8 文本模板。"""
    path = Path(__file__).resolve().parents[1] / "assets" / name
    return path.read_text(encoding="utf-8")


def _detect_newline(content: bytes) -> bytes:
    """从已有文件选择主换行符，避免增量修改无意义改写整份文本。"""
    if b"\r\n" in content:
        return b"\r\n"
    if b"\r" in content and b"\n" not in content:
        return b"\r"
    return b"\n"


def _render_with_newline(text: str, newline: bytes) -> bytes:
    """把模板统一为已有文件的换行风格后编码为 UTF-8。"""
    normalised = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return normalised.replace("\n", newline.decode("ascii")).encode("utf-8")


def _markdown_safe_text(value: str) -> str:
    """把仓库派生文本转成安全单行 Markdown 显示，避免名称改变 AGENTS 指令结构。"""
    escaped: list[str] = []
    for character in value:
        codepoint = ord(character)
        if character == "\\":
            escaped.append("\\\\")
        elif character == "\n":
            escaped.append("\\n")
        elif character == "\r":
            escaped.append("\\r")
        elif character == "\t":
            escaped.append("\\t")
        elif character in {"`", "<", ">"}:
            escaped.append(f"\\u{codepoint:04x}")
        elif codepoint < 0x20 or codepoint == 0x7F or character in {"\u0085", "\u2028", "\u2029"}:
            escaped.append(f"\\u{codepoint:04x}")
        else:
            escaped.append(character)
    return "".join(escaped)


def _bootstrap_fact_sources(root: Path) -> str:
    """列出初始化时真实存在的高价值事实入口，只提供导航而不推断技术栈。"""
    context = scan_project(root)
    grouped: dict[str, list[str]] = {}
    for item in context.get("documents", []):
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        kind = item.get("kind")
        if not isinstance(path, str) or not isinstance(kind, str):
            continue
        normalised = _normalise_relative_path(path)
        if normalised == AGENTS_FILENAME:
            continue
        if normalised.startswith(".agents/skills/") or normalised.startswith(".agents/changes/"):
            continue
        grouped.setdefault(kind, []).append(normalised)
    if not grouped:
        return "- 初始化扫描未发现可稳定列出的项目规则、Manifest、需求、Contract、Migration 或文档入口；后续任务按实际新增文件继续恢复事实。"
    labels = {
        "instructions": "项目规则",
        "manifest": "Manifest / Lock / Build",
        "requirements": "需求 / Spec / Roadmap",
        "contract": "Contract / Schema",
        "migration": "Migration",
        "documentation": "README / Architecture / Documentation",
    }
    lines: list[str] = []
    for kind in ("instructions", "manifest", "requirements", "contract", "migration", "documentation"):
        paths = sorted(set(grouped.get(kind, [])))
        if not paths:
            continue
        lines.append(f"- {labels[kind]}：")
        lines.extend(f"  - `{_markdown_safe_text(path)}`" for path in paths)
    return "\n".join(lines)


def _managed_asset_text() -> str:
    """读取 Runtime/项目 Bootstrap 的薄 managed block，并拒绝重新引入内部治理导航。"""
    text = _asset_text("AGENTS.managed.md")
    if text.count(AGENTS_MANAGED_START) != 1 or text.count(AGENTS_MANAGED_END) != 1:
        raise ValueError("AGENTS.managed.md managed marker 不完整或重复")
    if ".agents/skills/" in text or "ENTRY.md" in text or "router/SKILL.md" in text:
        raise ValueError("AGENTS.managed.md 不得暴露 Runtime 内部治理路径")
    return text


def _managed_block(newline: bytes) -> bytes:
    """渲染固定 Agent Skills managed block，并适配目标文件原有换行风格。"""
    return _render_with_newline(_managed_asset_text(), newline)


def _validate_managed_markers(content: bytes) -> tuple[int, int] | None:
    """校验 managed marker 唯一、成对且顺序正确；无 marker 时返回空值。"""
    start = AGENTS_MANAGED_START.encode("utf-8")
    end = AGENTS_MANAGED_END.encode("utf-8")
    start_count = content.count(start)
    end_count = content.count(end)
    if start_count == 0 and end_count == 0:
        return None
    if start_count != 1 or end_count != 1:
        raise ValueError("AGENTS.md 的 Agent Skills managed marker 不完整或重复，拒绝猜测性覆盖")
    start_index = content.find(start)
    end_index = content.find(end)
    if start_index < 0 or end_index < start_index:
        raise ValueError("AGENTS.md 的 Agent Skills managed marker 顺序错误，拒绝猜测性覆盖")
    return start_index, end_index + len(end)


def _updated_agents_content(root: Path, existing: bytes | None) -> bytes:
    """生成目标 AGENTS.md 内容；已有文件只追加或替换 managed block，其他字节保持不变。"""
    if existing is None:
        newline = b"\n"
        template = Template(_asset_text("AGENTS.template.md"))
        rendered = template.substitute(
            project_name=_markdown_safe_text(root.name or "Project"),
            managed_block=_managed_asset_text().rstrip("\r\n"),
            fact_sources=_bootstrap_fact_sources(root),
        )
        return _render_with_newline(rendered, newline) + newline

    try:
        existing.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("AGENTS.md 必须是 UTF-8 文本，无法安全增量修改") from error
    newline = _detect_newline(existing)
    block = _managed_block(newline)
    marker_range = _validate_managed_markers(existing)
    if marker_range is not None:
        start, end = marker_range
        return existing[:start] + block + existing[end:]
    if not existing:
        return block + newline
    if existing.endswith(newline + newline):
        separator = b""
    elif existing.endswith(newline):
        separator = newline
    else:
        separator = newline + newline
    return existing + separator + block + newline


def _gitignore_has_cache_rule(content: bytes) -> bool:
    """判断 .gitignore 是否已经显式忽略本地 project-context 缓存。"""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(".gitignore 必须是 UTF-8 文本，无法安全增量修改") from error
    accepted = {CACHE_IGNORE_RULE, "/" + CACHE_IGNORE_RULE}
    return any(line.strip() in accepted for line in text.splitlines())


def _updated_gitignore_content(existing: bytes | None) -> bytes:
    """增量补充本地缓存 ignore；已有规则和字节保持原样且重复执行幂等。"""
    if existing is not None and _gitignore_has_cache_rule(existing):
        return existing
    content = existing or b""
    newline = _detect_newline(content)
    entry = _render_with_newline(
        "# Agent local disposable cache\n" + CACHE_IGNORE_RULE,
        newline,
    )
    if not content:
        return entry + newline
    if content.endswith(newline + newline):
        separator = b""
    elif content.endswith(newline):
        separator = newline
    else:
        separator = newline + newline
    return content + separator + entry + newline


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    """在同目录写临时文件后原子替换目标，尽量保留已有普通文件权限。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_mode = path.stat().st_mode if path.exists() else None
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=path.name + ".", delete=False) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    try:
        if previous_mode is not None:
            os.chmod(temporary, previous_mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def bootstrap_project(root: str | Path) -> dict[str, str]:
    """创建或安全增量更新目标项目 AGENTS Overlay 和本地缓存 ignore，不生成项目语义猜测。"""
    project_root = Path(root).resolve()
    if not project_root.is_dir():
        raise NotADirectoryError(project_root)
    coding_skill = project_root / ".agents/skills/coding/SKILL.md"
    if coding_skill.is_symlink() or not coding_skill.is_file():
        raise FileNotFoundError(f"目标项目缺少已安装的 .agents/skills/coding/SKILL.md：{coding_skill}")
    entry = project_root / ".agents/skills/ENTRY.md"
    if entry.is_symlink() or not entry.is_file():
        raise FileNotFoundError(f"目标项目缺少已安装的 .agents/skills/ENTRY.md：{entry}")
    router = project_root / ".agents/skills/router/SKILL.md"
    if router.is_symlink() or not router.is_file():
        raise FileNotFoundError(f"目标项目缺少已安装的 .agents/skills/router/SKILL.md：{router}")

    agents_path = project_root / AGENTS_FILENAME
    gitignore_path = project_root / GITIGNORE_FILENAME
    for path in (agents_path, gitignore_path):
        if path.is_symlink():
            raise ValueError(f"Bootstrap 不修改符号链接文件：{path}")
        if path.exists() and not path.is_file():
            raise ValueError(f"Bootstrap 目标必须是普通文件：{path}")

    existing_agents = agents_path.read_bytes() if agents_path.exists() else None
    existing_gitignore = gitignore_path.read_bytes() if gitignore_path.exists() else None
    next_agents = _updated_agents_content(project_root, existing_agents)
    next_gitignore = _updated_gitignore_content(existing_gitignore)

    agents_mode = "created" if existing_agents is None else "unchanged"
    gitignore_mode = "created" if existing_gitignore is None else "unchanged"
    if existing_agents != next_agents:
        _atomic_write_bytes(agents_path, next_agents)
        if existing_agents is not None:
            agents_mode = "updated"
    if existing_gitignore != next_gitignore:
        _atomic_write_bytes(gitignore_path, next_gitignore)
        if existing_gitignore is not None:
            gitignore_mode = "updated"
    return {"agents": agents_mode, "gitignore": gitignore_mode}


def _validate_change_id(change_id: str) -> None:
    """校验 Coding Change ID 使用固定可排序格式。"""
    if not CHANGE_ID_PATTERN.fullmatch(change_id):
        raise ValueError(
            "change id 必须使用 CHG-YYYYMMDD-kebab-case 格式，例如 "
            "CHG-20260813-report-export"
        )


def _yaml_scalar(value: str) -> str:
    """使用 JSON 字符串编码生成兼容 YAML 的安全标量。"""
    return json.dumps(value, ensure_ascii=False)


def _yaml_list(_name: str, values: Sequence[str]) -> list[str]:
    """把字符串序列序列化为模板字段值所需的 YAML 列表片段。"""
    if not values:
        return ["[]"]
    return ["", *(f"  - {_yaml_scalar(value)}" for value in values)]


def _has_coding_change_layout(root: Path, relative_root: Path) -> bool:
    """判断专用 Coding 目录是否已经具有 active/archive 布局。"""
    candidate = root / relative_root
    return (candidate / "active").is_dir() or (candidate / "archive").is_dir()


def _raw_change_schema(path: Path) -> str | None:
    """只读取 CHANGE.md frontmatter 的 schema，用于识别顶层 changes 是否真是当前 Coding carrier。"""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() == "schema":
            return value.strip().strip("\"'") or None
    return None


def _top_level_change_documents(root: Path) -> list[Path]:
    """返回顶层 changes/active 与 archive 下现有 CHANGE.md。"""
    change_root = root / TOP_LEVEL_CHANGE_DIRECTORY
    return [
        *sorted((change_root / "active").glob("*/CHANGE.md")),
        *sorted((change_root / "archive").glob("*/*/CHANGE.md")),
    ]


def _has_current_top_level_coding_carrier(root: Path) -> bool:
    """只有顶层 changes 中存在记录且全部为当前 schema，才认作受支持 Coding carrier。"""
    documents = _top_level_change_documents(root)
    return bool(documents) and all(
        _raw_change_schema(path) == CHANGE_SCHEMA for path in documents
    )


def _has_foreign_change_governance(root: Path) -> bool:
    """检测已知外部治理或未被当前 schema 证明为 Coding carrier 的顶层 changes。"""
    if (root / "openspec").exists():
        return True
    top_level = root / TOP_LEVEL_CHANGE_DIRECTORY
    return top_level.exists() and not _has_current_top_level_coding_carrier(root)


def resolve_change_root(root: str | Path, *, for_create: bool = False) -> Path:
    """解析当前 Coding Change carrier；创建时遇到外部/未确认治理则拒绝静默写入。"""
    project_root = Path(root).resolve()
    if _has_coding_change_layout(project_root, DEFAULT_CHANGE_DIRECTORY):
        return project_root / DEFAULT_CHANGE_DIRECTORY
    if _has_current_top_level_coding_carrier(project_root):
        return project_root / TOP_LEVEL_CHANGE_DIRECTORY
    if for_create and _has_foreign_change_governance(project_root):
        raise ValueError(
            "检测到项目已有 OpenSpec、顶层 changes 或其他未确认治理，"
            "但没有证据表明它是当前 coding-change/v1 carrier；"
            "请先按项目规则确定 Requirement Traceability / Validation Matrix / Completion Audit 的承载方式，"
            "Coding 不会静默创建或污染平行 Change。"
        )
    return project_root / DEFAULT_CHANGE_DIRECTORY


def active_change_paths(root: str | Path) -> list[Path]:
    """返回当前 Coding carrier 中所有 Active CHANGE.md 路径。"""
    return sorted((resolve_change_root(root) / "active").glob("*/CHANGE.md"))


def archive_change_paths(root: str | Path) -> list[Path]:
    """返回当前 Coding carrier 中所有归档 CHANGE.md 路径。"""
    return sorted((resolve_change_root(root) / "archive").glob("*/*/CHANGE.md"))


def change_root_relative(root: str | Path) -> str:
    """返回当前 Coding carrier 相对仓库根的标准路径。"""
    project_root = Path(root).resolve()
    return _normalise_relative_path(resolve_change_root(project_root).relative_to(project_root))


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
    """在解析后的 Coding carrier 中以独占目录创建 `coding-change/v1` L2/L3 Change。"""
    _validate_change_id(change_id)
    normalised_level = level.upper()
    if normalised_level not in {"L2", "L3"}:
        raise ValueError("只有需要追踪的 L2 或 L3 任务可以创建 CHANGE.md")
    project_root = Path(root).resolve()
    today = _beijing_now().date().isoformat()
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
        "completion_gate": "required",
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
    active_directory = resolve_change_root(project_root, for_create=True) / "active"
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
    """解析 Coding Change frontmatter 中允许的标量和空列表形式。"""
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
    """严格校验当前 `coding-change/v1` 元数据，不接受旧 schema 或缺失门禁。"""
    missing = sorted((CHANGE_SCALAR_FIELDS | CHANGE_LIST_FIELDS) - set(metadata))
    if missing:
        raise ValueError(f"Change frontmatter 缺少字段：{', '.join(missing)}")
    for field in CHANGE_SCALAR_FIELDS:
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Change 字段 {field} 必须是非空字符串")
    if metadata["schema"] != CHANGE_SCHEMA:
        raise ValueError(f"不支持的 Change schema：{metadata['schema']}；当前只支持 {CHANGE_SCHEMA}")
    if metadata["completion_gate"] != "required":
        raise ValueError("Change completion_gate 必须为 required")
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
    """读取并严格校验 CHANGE.md 中当前支持的扁平 YAML frontmatter。"""
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
    """读取当前 Coding carrier 中仍处于进行状态的 Change 元数据。"""
    changes: list[dict[str, Any]] = []
    for path in active_change_paths(root):
        metadata = read_change_metadata(path)
        metadata["_path"] = _normalise_relative_path(path.relative_to(root))
        if str(metadata.get("status", "")).casefold() not in {"done"}:
            changes.append(metadata)
    return changes


def _normalised_values(metadata: dict[str, Any], key: str) -> list[str]:
    """返回 Change 字符串列表字段的去重、大小写无关比较值。"""
    value = metadata.get(key, [])
    if not isinstance(value, list):
        return []
    return sorted({str(item).strip().casefold() for item in value if str(item).strip()})


def _path_overlap(left: str, right: str) -> bool:
    """判断两个声明路径是否相同或存在父子覆盖关系。"""
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
    """检测进行中 Coding Change 在路径、Contract 和数据上的显式重叠。"""
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
    """以 UTF-8 友好的稳定格式打印 JSON。"""
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    """构造项目 Bootstrap、事实发现、Change 创建和冲突检查 CLI。"""
    parser = argparse.ArgumentParser(
        description="初始化项目 Agent Overlay、发现项目事实入口，并检查 Coding Change 的显式冲突。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="创建或安全增量更新目标项目 AGENTS.md 与缓存 ignore")
    bootstrap.add_argument("--root", default=".")
    bootstrap.add_argument("--json", action="store_true")

    discover = subparsers.add_parser("discover", help="创建或刷新本地项目发现缓存")
    discover.add_argument("--root", default=".")
    discover.add_argument("--force", action="store_true")
    discover.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="列出当前 Coding carrier 的进行中 Change 和冲突")
    status.add_argument("--root", default=".")
    status.add_argument("--json", action="store_true")

    new_change = subparsers.add_parser("new-change", help="原子创建一个 coding-change/v1 L2/L3 Change")
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

    conflicts = subparsers.add_parser("conflicts", help="检查当前 Coding carrier 中进行中 Change 的重叠")
    conflicts.add_argument("--root", default=".")
    conflicts.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行命令行入口。"""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    root = Path(arguments.root).resolve()
    try:
        if arguments.command == "bootstrap":
            result = bootstrap_project(root)
            if arguments.json:
                _json_print(result)
            else:
                print(f"AGENTS.md={result['agents']}；.gitignore={result['gitignore']}")
            return 0
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
        payload = {
            "change_root": change_root_relative(root),
            "changes": changes,
            "conflicts": conflicts,
        }
        if arguments.json:
            _json_print(payload)
        else:
            print(
                f"Coding Change carrier: {payload['change_root']}；"
                f"进行中 Change: {len(changes)}；显式冲突: {len(conflicts)}"
            )
        return 2 if conflicts else 0
    except (FileExistsError, NotADirectoryError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
