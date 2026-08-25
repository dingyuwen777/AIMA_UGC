#!/usr/bin/env python3
"""校验 RVC Change 的 Requirement Traceability 与 Completion Audit 门禁。"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence


COMPLETION_GATE_FIELD = "completion_gate"
COMPLETION_GATE_REQUIRED = "required"
TRACEABILITY_HEADING = "# Requirement Traceability"
COMPLETION_AUDIT_HEADING = "# Completion Audit"
TRACEABILITY_COLUMNS = ("ID", "Requirement", "Source", "Status", "Evidence")
REQUIREMENT_STATUSES = {
    "satisfied",
    "explicitly_deferred",
    "not_applicable",
    "not_satisfied",
}
AUDIT_ITEMS = {
    "upstream_re_read",
    "change_coverage",
    "reverse_audit",
    "unresolved_cleared",
}
PLACEHOLDERS = {
    "...",
    "n/a?",
    "tbd",
    "todo",
    "尚未执行",
    "尚未验证",
    "待实现",
    "待补充",
    "待确认",
    "待验证",
}
REQUIREMENT_ID_PATTERN = re.compile(r"^R[1-9][0-9]*$")
AUDIT_LINE_PATTERN = re.compile(r"^- \[([ xX])\]\s+([a-z_]+)[：:]\s*(.+)$")


def _load_rvc_module() -> Any:
    path = Path(__file__).with_name("rvc.py")
    spec = importlib.util.spec_from_file_location("reliable_vibe_coding_rvc", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 RVC parser: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RVC = _load_rvc_module()


def _normalise_relative_path(value: str | Path) -> str:
    path = str(value).replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return (
        bool(value)
        and not path.is_absolute()
        and ".." not in path.parts
        and re.match(r"^[A-Za-z]:", value) is None
    )


def _is_placeholder(value: str) -> bool:
    normalised = value.strip().strip("`").casefold()
    return not normalised or normalised in PLACEHOLDERS


def _raw_gate_required(path: Path) -> bool:
    """只识别新门禁 marker；legacy Change 不要求先通过新版 parser。"""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            return False
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() != COMPLETION_GATE_FIELD:
            continue
        return value.strip().strip("\"'").casefold() == COMPLETION_GATE_REQUIRED
    return False


def _body_after_frontmatter(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("缺少 Change frontmatter")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :])
    raise ValueError("Change frontmatter 未闭合")


def _section(body: str, heading: str) -> str | None:
    lines = body.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return None
    collected: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("# "):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def _table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator(cells: Sequence[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _parse_traceability(section: str) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    table_lines = [line for line in section.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 3:
        return [], ["Requirement Traceability 必须包含表头、分隔行和至少一条 Requirement"]
    header = _table_cells(table_lines[0])
    if tuple(header) != TRACEABILITY_COLUMNS:
        errors.append(
            "Requirement Traceability 表头必须严格为："
            + " | ".join(TRACEABILITY_COLUMNS)
        )
    separator = _table_cells(table_lines[1])
    if len(separator) != len(TRACEABILITY_COLUMNS) or not _is_separator(separator):
        errors.append("Requirement Traceability 第二行必须是 Markdown 表格分隔行")
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = _table_cells(line)
        if len(cells) != len(TRACEABILITY_COLUMNS):
            errors.append(f"Requirement Traceability 行列数错误：{line.strip()}")
            continue
        rows.append(dict(zip(TRACEABILITY_COLUMNS, cells, strict=True)))
    if not rows:
        errors.append("Requirement Traceability 至少需要一条 Requirement")
    return rows, errors


def _validate_source(root: Path, change_path: Path, source: str) -> str | None:
    value = source.strip().strip("`")
    if _is_placeholder(value):
        return f"Requirement Source 不能是占位值：{source}"
    if value.startswith(("user:", "external:")):
        prefix, _, payload = value.partition(":")
        if not payload.strip():
            return f"Requirement Source {prefix}: 后必须包含可识别来源"
        return None
    if value.startswith(("https://", "http://")):
        return None
    path_value = value.split("#", 1)[0].strip()
    path_value = _normalise_relative_path(path_value)
    if not _is_safe_relative_path(path_value):
        return f"Requirement Source 必须是安全仓库相对路径或显式 user/external 来源：{source}"
    candidate = root / path_value
    if not candidate.is_file():
        return f"Requirement Source 仓库文件不存在：{path_value}"
    try:
        if candidate.resolve() == change_path.resolve():
            return "当前 Change 不能把自身作为 Requirement Source"
    except OSError:
        return f"Requirement Source 无法解析：{path_value}"
    return None


def _validate_traceability(root: Path, change_path: Path, body: str) -> list[str]:
    section = _section(body, TRACEABILITY_HEADING)
    if section is None:
        return [f"缺少 {TRACEABILITY_HEADING}"]
    rows, errors = _parse_traceability(section)
    seen_ids: set[str] = set()
    for row in rows:
        requirement_id = row["ID"]
        if not REQUIREMENT_ID_PATTERN.fullmatch(requirement_id):
            errors.append(f"Requirement ID 必须使用 R1/R2/...：{requirement_id}")
        elif requirement_id in seen_ids:
            errors.append(f"Requirement ID 重复：{requirement_id}")
        seen_ids.add(requirement_id)

        requirement = row["Requirement"]
        if _is_placeholder(requirement):
            errors.append(f"{requirement_id} Requirement 不能为空或使用占位值")

        status = row["Status"]
        if status not in REQUIREMENT_STATUSES:
            errors.append(
                f"{requirement_id} Status 非法：{status}；只允许 "
                + ", ".join(sorted(REQUIREMENT_STATUSES))
            )
        elif status == "not_satisfied":
            errors.append(f"{requirement_id} 仍为 not_satisfied，不能进入 Ready/归档")

        source_error = _validate_source(root, change_path, row["Source"])
        if source_error:
            errors.append(f"{requirement_id} {source_error}")

        evidence = row["Evidence"]
        if _is_placeholder(evidence):
            errors.append(f"{requirement_id} Evidence 不能是占位值：{evidence}")
    return errors


def _validate_completion_audit(body: str) -> list[str]:
    section = _section(body, COMPLETION_AUDIT_HEADING)
    if section is None:
        return [f"缺少 {COMPLETION_AUDIT_HEADING}"]
    found: dict[str, bool] = {}
    errors: list[str] = []
    for line in section.splitlines():
        match = AUDIT_LINE_PATTERN.match(line.strip())
        if match is None:
            continue
        checked, item, description = match.groups()
        if item not in AUDIT_ITEMS:
            continue
        if item in found:
            errors.append(f"Completion Audit 项重复：{item}")
            continue
        if _is_placeholder(description):
            errors.append(f"Completion Audit {item} 缺少有效说明")
        found[item] = checked.casefold() == "x"
    for item in sorted(AUDIT_ITEMS):
        if item not in found:
            errors.append(f"Completion Audit 缺少项目：{item}")
        elif not found[item]:
            errors.append(f"Completion Audit 未完成：{item}")
    return errors


def _metadata(path: Path) -> dict[str, Any]:
    return RVC.read_change_metadata(path)


def _validate_ready_document(root: Path, path: Path) -> list[str]:
    body = _body_after_frontmatter(path)
    return [
        *_validate_traceability(root, path, body),
        *_validate_completion_audit(body),
    ]


def _active_paths(root: Path) -> list[Path]:
    return sorted((root / "changes" / "active").glob("*/CHANGE.md"))


def _archive_paths(root: Path) -> list[Path]:
    return sorted((root / "changes" / "archive").glob("*/*/CHANGE.md"))


def _git_diff_paths(root: Path, base: str, *, diff_filter: str) -> set[str]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--name-only",
            f"--diff-filter={diff_filter}",
            f"{base}...HEAD",
            "--",
            "changes/active",
            "changes/archive",
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
    return {_normalise_relative_path(line) for line in result.stdout.splitlines() if line.strip()}


def check_repository(
    root: Path,
    *,
    require_active_ready: bool = False,
    changed_since: str | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    legacy = 0
    gated = 0
    strict = 0
    changed = (
        _git_diff_paths(root, changed_since, diff_filter="ACMRTUXB")
        if changed_since
        else set()
    )
    added = _git_diff_paths(root, changed_since, diff_filter="A") if changed_since else set()

    for path in [*_active_paths(root), *_archive_paths(root)]:
        relative = _normalise_relative_path(path.relative_to(root))
        try:
            gate_required = _raw_gate_required(path)
        except OSError as exc:
            errors.append({"path": relative, "message": str(exc)})
            continue
        if not gate_required:
            if relative in added and relative.startswith("changes/active/"):
                errors.append(
                    {
                        "path": relative,
                        "message": "本 PR 新增的 Active Change 必须包含 completion_gate: required",
                    }
                )
            else:
                legacy += 1
            continue

        gated += 1
        try:
            metadata = _metadata(path)
        except (OSError, ValueError) as exc:
            errors.append({"path": relative, "message": str(exc)})
            continue

        archived = relative.startswith("changes/archive/")
        status = str(metadata.get("status", "")).casefold()
        is_changed_active = relative in changed and relative.startswith("changes/active/")
        must_be_ready = require_active_ready or is_changed_active

        if archived:
            if status != "done":
                errors.append(
                    {"path": relative, "message": "启用 Completion Gate 的归档 Change 必须为 done"}
                )
                continue
            must_validate = True
        else:
            if status == "done":
                errors.append(
                    {"path": relative, "message": "done Change 不得继续留在 changes/active/"}
                )
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
                document_errors = _validate_ready_document(root, path)
            except (OSError, ValueError) as exc:
                document_errors = [str(exc)]
            errors.extend({"path": relative, "message": message} for message in document_errors)

    return {
        "ok": not errors,
        "legacy": legacy,
        "gated": gated,
        "strict_checked": strict,
        "errors": errors,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检查 RVC Requirement Traceability / Completion Audit Ready 门禁。"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--require-active-ready",
        action="store_true",
        help="要求所有启用 Completion Gate 的 Active Change 都已 ready_for_review。",
    )
    parser.add_argument(
        "--changed-since",
        help="只要求从给定 Git base 到 HEAD 发生变化的 gated Active Change 已 Ready。",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
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
            f"gated={result['gated']}，strict={result['strict_checked']}，"
            f"legacy={result['legacy']}。"
        )
    else:
        for error in result["errors"]:
            print(f"ERROR {error['path']}: {error['message']}", file=sys.stderr)
        print(
            "Ready Check 失败："
            f"{len(result['errors'])} 个问题；legacy={result['legacy']}。",
            file=sys.stderr,
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
