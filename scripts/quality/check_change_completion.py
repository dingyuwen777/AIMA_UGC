#!/usr/bin/env python3
"""校验 AIMA 顶层 Change carrier 的当前记录与不可变历史边界。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHANGE_ROOT = Path("changes")
READY_CHECK = Path(".agents/skills/coding/scripts/ready_check.py")
CURRENT_SCHEMA = "coding-change/v1"
LEGACY_SCHEMA = "rvc-change/v1"
SCHEMA_PATTERN = re.compile(r"^schema:\s*([^#]+?)\s*$")
MISSING_ARCHIVE_SOURCE_PATTERN = re.compile(
    r"^R[1-9][0-9]* Requirement Source 仓库文件不存在：(.+)$"
)


@dataclass(frozen=True)
class DiffEntry:
    """表示一个与顶层 Change carrier 有关的 Git name-status 记录。"""

    status: str
    old_path: str | None
    new_path: str | None


def _normalise_relative_path(value: str | Path) -> str:
    """把路径规范为不带当前目录前缀的正斜杠形式。"""
    path = str(value).replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def _load_ready_check(path: Path) -> Any:
    """加载已安装的当前 validator，避免在项目内复制 schema/正文规则。"""
    if not path.is_file():
        raise RuntimeError(f"installed ready-check 不存在：{path}")
    spec = importlib.util.spec_from_file_location("aima_installed_ready_check", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 installed ready-check：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("_metadata", "_validate_ready_document"):
        if not callable(getattr(module, name, None)):
            raise RuntimeError(f"installed ready-check 缺少项目适配所需入口：{name}")
    return module


def _schema_from_text(text: str) -> str | None:
    """只读取 schema 用于 legacy 路由；当前字段仍交给 installed parser。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("缺少 Change frontmatter")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = SCHEMA_PATTERN.fullmatch(line.strip())
        if match:
            return match.group(1).strip().strip("\"'")
    else:
        raise ValueError("Change frontmatter 未闭合")
    return None


def _schema(path: Path) -> str | None:
    """读取工作树 Change 的 schema。"""
    return _schema_from_text(path.read_text(encoding="utf-8"))


def _change_paths(root: Path) -> tuple[Path, ...]:
    """显式枚举 AIMA 顶层 active/archive 下的全部 Change 文档。"""
    paths: list[Path] = []
    for relative in (CHANGE_ROOT / "active", CHANGE_ROOT / "archive"):
        directory = root / relative
        if directory.is_dir():
            paths.extend(directory.rglob("CHANGE.md"))
    return tuple(sorted(paths))


def _location(root: Path, path: Path) -> str:
    """返回 Change 的 active/archive 位置；层级异常时返回 invalid。"""
    parts = path.relative_to(root).parts
    if len(parts) == 4 and parts[:2] == ("changes", "active"):
        return "active"
    if len(parts) == 5 and parts[:2] == ("changes", "archive"):
        return "archive"
    return "invalid"


def _change_identity(relative: str) -> tuple[str, str] | None:
    """从规范 Change 路径提取位置与 Change ID。"""
    parts = Path(relative).parts
    if len(parts) == 4 and parts[:2] == ("changes", "active") and parts[-1] == "CHANGE.md":
        return "active", parts[2]
    if len(parts) == 5 and parts[:2] == ("changes", "archive") and parts[-1] == "CHANGE.md":
        return "archive", parts[3]
    return None


def _is_change_document(relative: str | None) -> bool:
    """判断 Git 路径是否为顶层 carrier 内的 Change 文档。"""
    return relative is not None and _change_identity(relative) is not None


def _git_diff_entries(root: Path, base: str) -> tuple[DiffEntry, ...]:
    """返回 base 到 HEAD 的 Change carrier name-status，保留删除与改名。"""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--name-status",
            "--find-renames",
            f"{base}...HEAD",
            "--",
            CHANGE_ROOT.as_posix(),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise ValueError(
            f"无法计算 Changed Change：git diff {base}...HEAD 失败：{result.stderr.strip()}"
        )

    entries: list[DiffEntry] = []
    for line in result.stdout.splitlines():
        columns = line.split("\t")
        if not columns or not columns[0]:
            continue
        status = columns[0][0]
        if status in {"R", "C"} and len(columns) == 3:
            entries.append(
                DiffEntry(
                    status=status,
                    old_path=_normalise_relative_path(columns[1]),
                    new_path=_normalise_relative_path(columns[2]),
                )
            )
        elif len(columns) == 2:
            path = _normalise_relative_path(columns[1])
            entries.append(
                DiffEntry(
                    status=status,
                    old_path=path if status == "D" else None,
                    new_path=None if status == "D" else path,
                )
            )
        else:
            raise ValueError(f"无法解析 git diff --name-status 输出：{line}")
    return tuple(entries)


def _git_show(root: Path, revision: str, relative: str) -> str:
    """读取指定 revision 的 Change 文档，用于删除/改名审计。"""
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{relative}"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise ValueError(f"无法读取 {revision}:{relative}：{result.stderr.strip()}")
    return result.stdout


def _git_last_path_revision(root: Path, relative: str) -> str | None:
    """返回当前路径最后一次被提交修改的 revision，供不可变归档恢复历史事实。"""
    result = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%H", "--", relative],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    revision = result.stdout.strip()
    return revision or None


def _git_path_exists_at_revision(root: Path, revision: str, relative: str) -> bool:
    """确认仓库相对路径在给定历史 revision 中真实存在，不从当前 HEAD 猜测。"""
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{revision}:{relative}"],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _preserve_historical_archive_sources(
    root: Path,
    change_path: Path,
    document_errors: Sequence[str],
) -> list[str]:
    """仅对已归档 Change 接受在其归档 revision 真实存在、后来才删除的来源。"""
    if not document_errors:
        return []
    change_relative = _normalise_relative_path(change_path.relative_to(root))
    archive_revision = _git_last_path_revision(root, change_relative)
    if archive_revision is None:
        return list(document_errors)

    preserved: list[str] = []
    for message in document_errors:
        match = MISSING_ARCHIVE_SOURCE_PATTERN.fullmatch(message)
        if match is None:
            preserved.append(message)
            continue
        source_relative = _normalise_relative_path(match.group(1))
        if not _git_path_exists_at_revision(root, archive_revision, source_relative):
            preserved.append(message)
    return preserved


def _changed_paths_and_errors(
    root: Path,
    base: str,
) -> tuple[set[str], list[dict[str, str]]]:
    """计算 PR 严格检查路径，并阻止删除或非法改名绕过。"""
    changed: set[str] = set()
    errors: list[dict[str, str]] = []
    for entry in _git_diff_entries(root, base):
        if entry.status == "D" and _is_change_document(entry.old_path):
            errors.append(
                {
                    "path": entry.old_path or "changes",
                    "message": "不得删除 Change 文档来规避完成门禁",
                }
            )
            continue

        if entry.status == "R" and _is_change_document(entry.old_path):
            assert entry.old_path is not None
            assert entry.new_path is not None
            old_schema = _schema_from_text(_git_show(root, base, entry.old_path))
            old_identity = _change_identity(entry.old_path)
            new_identity = _change_identity(entry.new_path)
            is_archive_transition = (
                old_schema == CURRENT_SCHEMA
                and old_identity is not None
                and new_identity is not None
                and old_identity[0] == "active"
                and new_identity[0] == "archive"
                and old_identity[1] == new_identity[1]
            )
            if not is_archive_transition:
                errors.append(
                    {
                        "path": entry.old_path,
                        "message": (
                            "只允许当前 Change 以同一 ID 从 active 移入 archive；"
                            "legacy 与其他改名不可变"
                        ),
                    }
                )
            if _is_change_document(entry.new_path):
                changed.add(entry.new_path)
            continue

        if _is_change_document(entry.new_path):
            assert entry.new_path is not None
            changed.add(entry.new_path)
    return changed, errors


def check_repository(
    root: Path,
    *,
    require_active_ready: bool = False,
    changed_since: str | None = None,
    ready_check_path: Path | None = None,
) -> dict[str, Any]:
    """检查 AIMA 顶层 Change，并返回稳定的 CI 诊断结构。"""
    root = root.resolve()
    validator_path = (ready_check_path or root / READY_CHECK).resolve()
    validator = _load_ready_check(validator_path)
    errors: list[dict[str, str]] = []
    gated = 0
    strict = 0
    legacy = 0
    changed: set[str] = set()
    if changed_since:
        changed, diff_errors = _changed_paths_and_errors(root, changed_since)
        errors.extend(diff_errors)

    seen_current_ids: dict[str, str] = {}
    for path in _change_paths(root):
        relative = _normalise_relative_path(path.relative_to(root))
        location = _location(root, path)
        if location == "invalid":
            errors.append(
                {
                    "path": relative,
                    "message": (
                        "Change 必须位于 changes/active/<ID> 或 changes/archive/<year-month>/<ID>"
                    ),
                }
            )
            continue

        try:
            schema = _schema(path)
        except (OSError, ValueError) as exc:
            errors.append({"path": relative, "message": str(exc)})
            continue

        if schema in {LEGACY_SCHEMA, None}:
            legacy += 1
            if location != "archive":
                errors.append(
                    {
                        "path": relative,
                        "message": "legacy Change 只允许保留在 archive，不得位于 active",
                    }
                )
            elif relative in changed:
                errors.append({"path": relative, "message": "legacy Change 是不可变历史，不得修改"})
            continue

        if schema != CURRENT_SCHEMA:
            errors.append({"path": relative, "message": f"不支持的 Change schema：{schema}"})
            continue

        gated += 1
        try:
            metadata = validator._metadata(path)
        except (OSError, ValueError) as exc:
            errors.append({"path": relative, "message": str(exc)})
            continue

        change_id = str(metadata.get("id", ""))
        previous = seen_current_ids.get(change_id)
        if previous is not None:
            errors.append(
                {
                    "path": relative,
                    "message": f"当前 Change ID 重复；另一份位于 {previous}",
                }
            )
            continue
        seen_current_ids[change_id] = relative

        status = str(metadata.get("status", "")).casefold()
        must_be_ready = require_active_ready or relative in changed
        if location == "archive":
            if status != "done":
                errors.append({"path": relative, "message": "归档 Coding Change 必须为 done"})
                continue
            must_validate = True
        else:
            if status == "done":
                errors.append({"path": relative, "message": "done Change 不得继续留在 active/"})
                continue
            if must_be_ready and status != "ready_for_review":
                errors.append(
                    {
                        "path": relative,
                        "message": (
                            "当前 PR/主分支要求 Active Change 完成门禁；"
                            f"状态必须为 ready_for_review，当前为 {status}"
                        ),
                    }
                )
                continue
            must_validate = status == "ready_for_review" or must_be_ready

        if must_validate:
            strict += 1
            try:
                document_errors = validator._validate_ready_document(root, path)
                if location == "archive":
                    document_errors = _preserve_historical_archive_sources(
                        root,
                        path,
                        document_errors,
                    )
            except (OSError, ValueError) as exc:
                document_errors = [str(exc)]
            errors.extend({"path": relative, "message": message} for message in document_errors)

    return {
        "ok": not errors,
        "change_root": CHANGE_ROOT.as_posix(),
        "gated": gated,
        "strict_checked": strict,
        "legacy": legacy,
        "errors": errors,
    }


def _build_parser() -> argparse.ArgumentParser:
    """构造 AIMA Change 完成门禁参数。"""
    parser = argparse.ArgumentParser(
        description="检查 AIMA 顶层 Change carrier 与 legacy 历史边界。"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--require-active-ready", action="store_true")
    parser.add_argument("--changed-since")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行项目门禁，并输出兼容人工和 CI 读取的结果。"""
    arguments = _build_parser().parse_args(argv)
    root = Path(arguments.root).resolve()
    if not root.is_dir():
        print(f"error: root 不是目录：{root}", file=sys.stderr)
        return 1
    try:
        result = check_repository(
            root,
            require_active_ready=arguments.require_active_ready,
            changed_since=arguments.changed_since,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if arguments.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    elif result["ok"]:
        print(
            "Ready Check 通过："
            f"carrier={result['change_root']}，gated={result['gated']}，"
            f"strict={result['strict_checked']}，legacy={result['legacy']}。"
        )
    else:
        for error in result["errors"]:
            print(f"ERROR {error['path']}: {error['message']}", file=sys.stderr)
        print(
            "Ready Check 失败："
            f"carrier={result['change_root']}，gated={result['gated']}，"
            f"strict={result['strict_checked']}，legacy={result['legacy']}，"
            f"{len(result['errors'])} 个问题。",
            file=sys.stderr,
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
