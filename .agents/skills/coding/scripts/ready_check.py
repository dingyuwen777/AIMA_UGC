#!/usr/bin/env python3
"""校验 Coding Change 的需求追溯与完成审计门禁。"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence


TRACEABILITY_HEADINGS = ("# 需求追溯", "# Requirement Traceability")
COMPLETION_AUDIT_HEADINGS = ("# 完成审计", "# Completion Audit")
TRACEABILITY_COLUMNS = ("ID", "Requirement", "Source", "Status", "Evidence")
TRACEABILITY_COLUMN_VARIANTS = {
    ("编号", "要求", "来源", "状态", "证据"): TRACEABILITY_COLUMNS,
    TRACEABILITY_COLUMNS: TRACEABILITY_COLUMNS,
}
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
ISSUE_REFERENCE_PATTERN = re.compile(r"^#[1-9][0-9]*$")
ACCEPTANCE_BINDING_PATTERN = re.compile(
    r"^(?P<owner>.+?)(?:\s*/\s*|#)(?P<acceptance>AC[1-9][0-9]*)$",
    re.IGNORECASE,
)


def _load_coding_module() -> Any:
    """从同目录加载 Coding CLI 解析器，避免依赖额外包安装。"""
    path = Path(__file__).with_name("coding.py")
    spec = importlib.util.spec_from_file_location("coding_skill_tooling", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 Coding parser: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CODING = _load_coding_module()


def _normalise_relative_path(value: str | Path) -> str:
    """把路径规范成仓库相对的正斜杠形式。"""
    path = str(value).replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def _is_safe_relative_path(value: str) -> bool:
    """判断 Requirement Source 是否为不逃逸仓库的安全相对路径。"""
    path = Path(value)
    return (
        bool(value)
        and not path.is_absolute()
        and ".." not in path.parts
        and re.match(r"^[A-Za-z]:", value) is None
    )


def _is_placeholder(value: str) -> bool:
    """判断文本是否为空或仍是 Ready 阶段禁止保留的占位值。"""
    normalised = value.strip().strip("`").casefold()
    return not normalised or normalised in PLACEHOLDERS


def _split_acceptance_binding(value: str) -> tuple[str, str] | None:
    """解析 `上游 Owner / AC1` 或 `上游Owner#AC1` 稳定 Acceptance 绑定。"""
    match = ACCEPTANCE_BINDING_PATTERN.fullmatch(value.strip().strip("`"))
    if match is None:
        return None
    owner = match.group("owner").strip()
    acceptance = match.group("acceptance").upper()
    if not owner:
        return None
    return owner, acceptance


def _body_after_frontmatter(path: Path) -> str:
    """返回 CHANGE.md frontmatter 之后的正文。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("缺少 Change frontmatter")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :])
    raise ValueError("Change frontmatter 未闭合")


def _section(body: str, headings: Sequence[str]) -> str | None:
    """从 Change 正文中提取任一兼容一级标题对应的内容。"""
    lines = body.splitlines()
    heading_set = set(headings)
    try:
        start = next(
            index for index, line in enumerate(lines) if line.strip() in heading_set
        )
    except StopIteration:
        return None
    collected: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("# "):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def _table_cells(line: str) -> list[str]:
    """解析简单 Markdown 表格行并返回单元格。"""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator(cells: Sequence[str]) -> bool:
    """判断单元格是否组成合法 Markdown 表格分隔行。"""
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _parse_traceability(section: str) -> tuple[list[dict[str, str]], list[str]]:
    """解析中英文兼容的需求追溯表并返回规范化行数据和结构错误。"""
    errors: list[str] = []
    table_lines = [line for line in section.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 3:
        return [], ["需求追溯必须包含表头、分隔行和至少一条要求"]
    header = tuple(_table_cells(table_lines[0]))
    canonical_columns = TRACEABILITY_COLUMN_VARIANTS.get(header)
    if canonical_columns is None:
        errors.append(
            "需求追溯表头必须严格为：编号 | 要求 | 来源 | 状态 | 证据"
            "（历史 Change 仍兼容 ID | Requirement | Source | Status | Evidence）"
        )
        canonical_columns = TRACEABILITY_COLUMNS
    separator = _table_cells(table_lines[1])
    if len(separator) != len(TRACEABILITY_COLUMNS) or not _is_separator(separator):
        errors.append("需求追溯第二行必须是 Markdown 表格分隔行")
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = _table_cells(line)
        if len(cells) != len(TRACEABILITY_COLUMNS):
            errors.append(f"需求追溯行列数错误：{line.strip()}")
            continue
        rows.append(dict(zip(canonical_columns, cells, strict=True)))
    if not rows:
        errors.append("需求追溯至少需要一条要求")
    return rows, errors


def _validate_source(root: Path, change_path: Path, source: str) -> str | None:
    """校验 Requirement Source 可识别且不会引用当前 Change 自身。"""
    value = source.strip().strip("`")
    if _is_placeholder(value):
        return f"Requirement Source 不能是占位值：{source}"

    binding = _split_acceptance_binding(value)
    owner_value = binding[0] if binding is not None else value

    if ISSUE_REFERENCE_PATTERN.fullmatch(owner_value):
        # Ready validator 只负责稳定引用的机器形状；Issue 的真实存在性由 PR/项目 Requirement Source gate 验证。
        return None

    if owner_value.startswith(("user:", "external:")):
        prefix, _, payload = owner_value.partition(":")
        if not payload.strip():
            return f"Requirement Source {prefix}: 后必须包含可识别来源"
        return None
    if owner_value.startswith(("https://", "http://")):
        return None

    path_value = owner_value.split("#", 1)[0].strip()
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


def _validate_traceability(
    root: Path,
    change_path: Path,
    body: str,
    *,
    require_acceptance_binding: bool = False,
) -> list[str]:
    """校验需求追溯的 ID、状态、来源、稳定 Acceptance 绑定和 Evidence。"""
    section = _section(body, TRACEABILITY_HEADINGS)
    if section is None:
        return ["缺少 # 需求追溯（历史 Change 兼容 # Requirement Traceability）"]
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

        source_value = row["Source"].strip().strip("`")
        source_error = _validate_source(root, change_path, source_value)
        if source_error:
            errors.append(f"{requirement_id} {source_error}")
        elif require_acceptance_binding and _split_acceptance_binding(source_value) is None:
            errors.append(
                f"{requirement_id} Source 必须绑定稳定 Acceptance，例如 `#123 / AC1`、"
                "`specs/feature.md#AC1` 或项目等价稳定标识"
            )

        evidence = row["Evidence"]
        if _is_placeholder(evidence):
            errors.append(f"{requirement_id} Evidence 不能是占位值：{evidence}")
    return errors


def _validate_completion_audit(body: str) -> list[str]:
    """校验完成审计四项均有有效说明并已勾选。"""
    section = _section(body, COMPLETION_AUDIT_HEADINGS)
    if section is None:
        return ["缺少 # 完成审计（历史 Change 兼容 # Completion Audit）"]
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
            errors.append(f"完成审计项重复：{item}")
            continue
        if _is_placeholder(description):
            errors.append(f"完成审计 {item} 缺少有效说明")
        found[item] = checked.casefold() == "x"
    for item in sorted(AUDIT_ITEMS):
        if item not in found:
            errors.append(f"完成审计缺少项目：{item}")
        elif not found[item]:
            errors.append(f"完成审计未完成：{item}")
    return errors


def _metadata(path: Path) -> dict[str, Any]:
    """复用 Coding CLI 的当前 `coding-change/v1` frontmatter 解析规则。"""
    return CODING.read_change_metadata(path)


def _validate_ready_document(
    root: Path,
    path: Path,
    *,
    require_acceptance_binding: bool = False,
) -> list[str]:
    """校验一个 Ready/Archive Change 的需求追溯表和完成审计正文。"""
    body = _body_after_frontmatter(path)
    return [
        *_validate_traceability(
            root,
            path,
            body,
            require_acceptance_binding=require_acceptance_binding,
        ),
        *_validate_completion_audit(body),
    ]


def _change_root_relative(root: Path) -> str:
    """返回当前 Coding Change carrier 的仓库相对路径。"""
    return CODING.change_root_relative(root)


def _git_diff_paths(root: Path, base: str, *, diff_filter: str) -> set[str]:
    """返回 base 到 HEAD 之间当前 Coding carrier 内符合过滤条件的变更路径。"""
    change_root = _change_root_relative(root)
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
            f"{change_root}/active",
            f"{change_root}/archive",
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


def _is_archived(root: Path, path: Path) -> bool:
    """判断 Change 路径是否位于当前 carrier 的 archive 目录。"""
    relative = path.relative_to(CODING.resolve_change_root(root))
    return bool(relative.parts and relative.parts[0] == "archive")


def _is_active(root: Path, path: Path) -> bool:
    """判断 Change 路径是否位于当前 carrier 的 active 目录。"""
    relative = path.relative_to(CODING.resolve_change_root(root))
    return bool(relative.parts and relative.parts[0] == "active")


def check_repository(
    root: Path,
    *,
    require_active_ready: bool = False,
    changed_since: str | None = None,
) -> dict[str, Any]:
    """检查当前 Coding carrier 中全部 Change 的 schema、状态和 Ready 语义门禁。"""
    errors: list[dict[str, str]] = []
    gated = 0
    strict = 0
    changed = (
        _git_diff_paths(root, changed_since, diff_filter="ACMRTUXB")
        if changed_since
        else set()
    )

    active_paths = CODING.active_change_paths(root)
    archive_paths = CODING.archive_change_paths(root)
    for path in [*active_paths, *archive_paths]:
        relative = _normalise_relative_path(path.relative_to(root))
        gated += 1
        try:
            metadata = _metadata(path)
        except (OSError, ValueError) as exc:
            errors.append({"path": relative, "message": str(exc)})
            continue

        archived = _is_archived(root, path)
        active = _is_active(root, path)
        status = str(metadata.get("status", "")).casefold()
        is_changed_active = relative in changed and active
        must_be_ready = require_active_ready or is_changed_active

        if archived:
            if status != "done":
                errors.append(
                    {"path": relative, "message": "归档 Coding Change 必须为 done"}
                )
                continue
            must_validate = True
            # 历史 untouched archive 不因新稳定 Acceptance 语法被强制迁移；当前变更触及的 archive 才进入新门禁。
            require_acceptance_binding = bool(changed_since and relative in changed)
        else:
            if not active:
                errors.append({"path": relative, "message": "Change 不位于 active 或 archive 目录"})
                continue
            if status == "done":
                errors.append(
                    {"path": relative, "message": "done Change 不得继续留在 active/"}
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
            require_acceptance_binding = must_validate

        if must_validate:
            strict += 1
            try:
                document_errors = _validate_ready_document(
                    root,
                    path,
                    require_acceptance_binding=require_acceptance_binding,
                )
            except (OSError, ValueError) as exc:
                document_errors = [str(exc)]
            errors.extend({"path": relative, "message": message} for message in document_errors)

    return {
        "ok": not errors,
        "change_root": _change_root_relative(root),
        "gated": gated,
        "strict_checked": strict,
        "errors": errors,
    }


def _build_parser() -> argparse.ArgumentParser:
    """构造 Coding 完成门禁的命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="检查 coding-change/v1 需求追溯 / 完成审计就绪门禁。"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--require-active-ready",
        action="store_true",
        help="要求当前 Coding carrier 的所有 Active Change 都已 ready_for_review。",
    )
    parser.add_argument(
        "--changed-since",
        help="只额外要求从给定 Git base 到 HEAD 发生变化的 Active Change 已 Ready。",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 Coding Ready Check CLI 并按检查结果返回退出码。"""
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
            f"strict={result['strict_checked']}。"
        )
    else:
        for error in result["errors"]:
            print(f"ERROR {error['path']}: {error['message']}", file=sys.stderr)
        print(
            "Ready Check 失败："
            f"carrier={result['change_root']}，{len(result['errors'])} 个问题。",
            file=sys.stderr,
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
