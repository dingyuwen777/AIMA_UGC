#!/usr/bin/env python3
"""解析正式 Release 可使用的主分支检查证据，并对归档继承执行失败关闭校验。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

REQUIRED_CHECKS = frozenset(
    {
        "CI Gate",
        "Compose Golden Path",
        "Requirement Traceability and Completion Audit",
    }
)
ARCHIVE_MESSAGE_PATTERN = re.compile(r"^归档 Change：(?P<change_id>CHG-[A-Za-z0-9-]+) \[skip ci\]$")
ACTIVE_PATH_PATTERN = re.compile(r"^changes/active/(?P<change_id>CHG-[A-Za-z0-9-]+)/CHANGE\.md$")
ARCHIVE_PATH_PATTERN = re.compile(
    r"^changes/archive/(?P<month>[0-9]{4}-[0-9]{2})/"
    r"(?P<change_id>CHG-[A-Za-z0-9-]+)/CHANGE\.md$"
)
FRONTMATTER_FIELD_PATTERN = re.compile(r"^(?P<key>[A-Za-z_]+):(?P<value>.*)$")


class ReleaseEvidenceError(ValueError):
    """表示 Release 检查证据缺失、不绿或无法安全继承。"""


def _git(root: Path, *arguments: str) -> str:
    """执行只读 Git 命令，并把失败转换为稳定的 Release 证据错误。"""
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
        raise ReleaseEvidenceError(f"Git 证据读取失败：{detail}")
    return result.stdout


def _frontmatter_fields(text: str) -> dict[str, str]:
    """读取归档校验所需的扁平 frontmatter 字段。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ReleaseEvidenceError("Change 缺少 frontmatter 起始分隔符")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        match = FRONTMATTER_FIELD_PATTERN.match(line)
        if match is not None:
            fields[match.group("key")] = match.group("value").strip().strip("\"'")
    raise ReleaseEvidenceError("Change frontmatter 未闭合")


def _freeze_lifecycle(text: str, *, merged_date: str) -> str:
    """按 Archivist 规则只冻结 status 和 updated，供全文确定性比较。"""
    lines = text.splitlines(keepends=True)
    in_frontmatter = False
    closed = False
    status_seen = False
    updated_seen = False
    result = list(lines)

    for index, line in enumerate(lines):
        plain = line.rstrip("\r\n")
        if index == 0 and plain.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter and plain.strip() == "---":
            closed = True
            break
        if not in_frontmatter:
            continue
        match = FRONTMATTER_FIELD_PATTERN.match(plain)
        if match is None:
            continue
        key = match.group("key")
        newline = line[len(plain) :]
        if key == "status":
            current = match.group("value").strip().strip("\"'").casefold()
            if current != "ready_for_review":
                raise ReleaseEvidenceError(
                    f"归档父提交 Change 状态必须是 ready_for_review，当前为 {current or '<empty>'}"
                )
            result[index] = f"status: done{newline}"
            status_seen = True
        elif key == "updated":
            result[index] = f"updated: {merged_date}{newline}"
            updated_seen = True

    if not closed:
        raise ReleaseEvidenceError("Change frontmatter 未闭合")
    if not status_seen or not updated_seen:
        raise ReleaseEvidenceError("Change 缺少可确定性冻结的 status/updated 字段")
    return "".join(result)


def _latest_required_checks(
    payload: Mapping[str, Any],
) -> dict[str, tuple[str, str | None, str | None]]:
    """按完成时间选择每个 required check 的最新实例。"""
    runs = payload.get("check_runs", [])
    if not isinstance(runs, list):
        raise ReleaseEvidenceError("GitHub check-runs 响应缺少数组字段 check_runs")
    latest: dict[str, tuple[str, str | None, str | None]] = {}
    for raw in runs:
        if not isinstance(raw, Mapping):
            continue
        name = raw.get("name")
        if not isinstance(name, str) or name not in REQUIRED_CHECKS:
            continue
        timestamp = raw.get("completed_at") or raw.get("started_at") or ""
        if not isinstance(timestamp, str):
            timestamp = ""
        previous = latest.get(name)
        if previous is None or timestamp > previous[0]:
            status = raw.get("status")
            conclusion = raw.get("conclusion")
            latest[name] = (
                timestamp,
                status if isinstance(status, str) else None,
                conclusion if isinstance(conclusion, str) else None,
            )
    return latest


def _guarded_archive_parent(root: Path, release_sha: str) -> str:
    """证明 release_sha 只是单一 Change 的确定性归档，并返回唯一父提交。"""
    root = root.resolve()
    resolved_release = _git(root, "rev-parse", "--verify", f"{release_sha}^{{commit}}").strip()
    parents = _git(root, "show", "-s", "--format=%P", resolved_release).split()
    if len(parents) != 1:
        raise ReleaseEvidenceError("可继承的归档提交必须恰好有一个父提交")
    parent_sha = parents[0]

    message = _git(root, "show", "-s", "--format=%B", resolved_release).strip()
    message_match = ARCHIVE_MESSAGE_PATTERN.fullmatch(message)
    if message_match is None:
        raise ReleaseEvidenceError("当前提交不符合专用 Archivist 的归档提交消息")
    change_id = message_match.group("change_id")

    diff_lines = [
        line
        for line in _git(
            root,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "--no-renames",
            "-r",
            parent_sha,
            resolved_release,
        ).splitlines()
        if line.strip()
    ]
    if len(diff_lines) != 2:
        raise ReleaseEvidenceError("归档提交必须恰好包含两个路径：Active 删除与 Archive 新增")

    paths_by_status: dict[str, str] = {}
    for line in diff_lines:
        try:
            status, relative = line.split("\t", 1)
        except ValueError as exc:
            raise ReleaseEvidenceError(f"无法解析归档路径变更：{line}") from exc
        if status in paths_by_status:
            raise ReleaseEvidenceError("归档提交必须恰好包含一个删除和一个新增路径")
        paths_by_status[status] = relative
    if set(paths_by_status) != {"A", "D"}:
        raise ReleaseEvidenceError("归档提交必须恰好包含一个删除和一个新增路径")

    source_relative = paths_by_status["D"]
    target_relative = paths_by_status["A"]
    source_match = ACTIVE_PATH_PATTERN.fullmatch(source_relative)
    target_match = ARCHIVE_PATH_PATTERN.fullmatch(target_relative)
    if source_match is None or target_match is None:
        raise ReleaseEvidenceError("归档路径不符合 changes/active → changes/archive 约束")
    if source_match.group("change_id") != change_id or target_match.group("change_id") != change_id:
        raise ReleaseEvidenceError("归档消息、Active 路径与 Archive 路径的 Change ID 不一致")

    source_text = _git(root, "show", f"{parent_sha}:{source_relative}")
    target_text = _git(root, "show", f"{resolved_release}:{target_relative}")
    source_fields = _frontmatter_fields(source_text)
    target_fields = _frontmatter_fields(target_text)
    if (
        source_fields.get("schema") != "coding-change/v1"
        or source_fields.get("id") != change_id
        or source_fields.get("status", "").casefold() != "ready_for_review"
    ):
        raise ReleaseEvidenceError("归档父提交不是匹配的 coding-change/v1 ready_for_review Change")
    if (
        target_fields.get("schema") != "coding-change/v1"
        or target_fields.get("id") != change_id
        or target_fields.get("status", "").casefold() != "done"
    ):
        raise ReleaseEvidenceError("归档结果不是匹配的 coding-change/v1 done Change")

    updated = target_fields.get("updated", "")
    try:
        updated_date = date.fromisoformat(updated)
    except ValueError as exc:
        raise ReleaseEvidenceError("归档结果 updated 不是合法日期") from exc
    if updated_date.strftime("%Y-%m") != target_match.group("month"):
        raise ReleaseEvidenceError("归档月份与 Change updated 日期不一致")
    if target_text != _freeze_lifecycle(source_text, merged_date=updated):
        raise ReleaseEvidenceError("归档结果不等于父提交 Change 的确定性冻结结果")
    return parent_sha


def resolve_evidence_sha(
    root: Path, release_sha: str, release_check_runs: Mapping[str, Any]
) -> str:
    """选择当前发布提交或唯一合法归档父提交作为 required-check 证据 revision。"""
    latest = _latest_required_checks(release_check_runs)
    if len(latest) == len(REQUIRED_CHECKS):
        return _git(root.resolve(), "rev-parse", "--verify", f"{release_sha}^{{commit}}").strip()
    if latest:
        present = ", ".join(sorted(latest))
        missing = ", ".join(sorted(REQUIRED_CHECKS - latest.keys()))
        raise ReleaseEvidenceError(
            f"当前发布提交的 required checks 仅部分存在；present={present}; missing={missing}"
        )
    return _guarded_archive_parent(root, release_sha)


def verify_required_checks(payload: Mapping[str, Any]) -> None:
    """确认三项 required checks 的最新实例均已完成且成功。"""
    latest = _latest_required_checks(payload)
    failures: list[str] = []
    for name in sorted(REQUIRED_CHECKS):
        if name not in latest:
            failures.append(f"{name}: missing")
            continue
        _, status, conclusion = latest[name]
        if status != "completed" or conclusion != "success":
            failures.append(f"{name}: status={status}, conclusion={conclusion}")
    if failures:
        raise ReleaseEvidenceError(
            "Release gate failed; required main checks are not green:\n- " + "\n- ".join(failures)
        )


def _load_json(path: Path) -> Mapping[str, Any]:
    """读取 GitHub API JSON 响应。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseEvidenceError(f"无法读取 check-runs JSON：{path}") from exc
    if not isinstance(payload, Mapping):
        raise ReleaseEvidenceError("check-runs JSON 顶层必须是对象")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    """构造 Release 证据解析 CLI。"""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    resolve = subparsers.add_parser("resolve")
    resolve.add_argument("--root", default=".")
    resolve.add_argument("--release-sha", required=True)
    resolve.add_argument("--check-runs-file", required=True, type=Path)
    resolve.add_argument("--github-output", required=True, type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--check-runs-file", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行 evidence resolve/verify，并以非零退出码拒绝不安全发布。"""
    arguments = _build_parser().parse_args(argv)
    try:
        payload = _load_json(arguments.check_runs_file)
        if arguments.command == "resolve":
            evidence_sha = resolve_evidence_sha(
                Path(arguments.root), arguments.release_sha, payload
            )
            release_sha = _git(
                Path(arguments.root).resolve(),
                "rev-parse",
                "--verify",
                f"{arguments.release_sha}^{{commit}}",
            ).strip()
            inherited = evidence_sha != release_sha
            with arguments.github_output.open("a", encoding="utf-8") as output:
                output.write(f"evidence_sha={evidence_sha}\n")
                output.write(f"inherited={str(inherited).lower()}\n")
            print(
                json.dumps(
                    {
                        "release_sha": release_sha,
                        "evidence_sha": evidence_sha,
                        "inherited": inherited,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            verify_required_checks(payload)
            print("Release gate passed: required main checks are green.")
    except (OSError, ReleaseEvidenceError) as exc:
        print(f"RELEASE_EVIDENCE_ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
