#!/usr/bin/env python3
"""在 Implementation PR 合并后确定性归档该 PR 携带的 AIMA Change。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CHANGE_ROOT = Path("changes")
CURRENT_SCHEMA = "coding-change/v1"
ACTIVE_CHANGE_PATTERN = re.compile(r"^changes/active/(?P<change_id>CHG-[^/]+)/CHANGE\.md$")
FRONTMATTER_FIELD_PATTERN = re.compile(r"^(?P<key>[A-Za-z_]+):(?P<rest>.*)$")


def _beijing_timezone() -> tzinfo:
    """优先使用 IANA 北京时区；无系统 tzdata 时为现代归档日期退化到 UTC+08:00。"""
    try:
        return ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8), name="Asia/Shanghai")


BEIJING = _beijing_timezone()


class ArchiveChangeError(ValueError):
    """表示 Change 自动归档无法安全、唯一或确定性执行。"""


@dataclass(frozen=True)
class ChangeMetadata:
    """表示归档流程实际需要的最小 Change frontmatter。"""

    schema: str
    change_id: str
    status: str


@dataclass(frozen=True)
class ArchiveResult:
    """表示一次归档尝试的稳定结果。"""

    changed: bool
    change_id: str | None
    source: str | None
    target: str | None
    reason: str

    def as_dict(self) -> dict[str, object]:
        """返回适合 Workflow/测试消费的 JSON 结构。"""
        return {
            "changed": self.changed,
            "change_id": self.change_id,
            "source": self.source,
            "target": self.target,
            "reason": self.reason,
        }


def _normalise_path(value: str) -> str:
    """把 GitHub changed-file 路径规范为仓库相对正斜杠形式。"""
    path = value.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def load_changed_paths(path: Path) -> tuple[str, ...]:
    """读取 Workflow 写出的 PR changed-file 列表并保持去重顺序。"""
    if not path.is_file():
        raise ArchiveChangeError(f"changed paths 文件不存在：{path}")
    seen: set[str] = set()
    values: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = _normalise_path(raw)
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return tuple(values)


def select_change(changed_paths: Sequence[str]) -> tuple[str, str] | None:
    """从 merged PR changed files 中唯一选择 current Change 的 Active 路径。"""
    matches: list[tuple[str, str]] = []
    for relative in changed_paths:
        match = ACTIVE_CHANGE_PATTERN.fullmatch(_normalise_path(relative))
        if match is not None:
            matches.append((match.group("change_id"), _normalise_path(relative)))
    if not matches:
        return None
    if len(matches) != 1:
        joined = ", ".join(path for _, path in matches)
        raise ArchiveChangeError(
            "一个 Implementation PR 只能由归档自动化确定性处理一个 Active Change；"
            f"当前发现 {len(matches)} 个：{joined}"
        )
    return matches[0]


def _frontmatter_bounds(lines: list[str]) -> tuple[int, int]:
    """返回 Change YAML frontmatter 的起止行索引。"""
    if not lines or lines[0].strip() != "---":
        raise ArchiveChangeError("Change 缺少 frontmatter 起始分隔符")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return 0, index
    raise ArchiveChangeError("Change frontmatter 未闭合")


def parse_metadata(text: str) -> ChangeMetadata:
    """解析归档流程所需字段，不引入额外 YAML 运行依赖。"""
    lines = text.splitlines()
    _, end = _frontmatter_bounds(lines)
    values: dict[str, str] = {}
    for line in lines[1:end]:
        match = FRONTMATTER_FIELD_PATTERN.match(line)
        if match is None:
            continue
        key = match.group("key")
        if key in {"schema", "id", "status"}:
            values[key] = match.group("rest").strip().strip("\"'")
    missing = [key for key in ("schema", "id", "status") if not values.get(key)]
    if missing:
        raise ArchiveChangeError("Change 缺少归档必需字段：" + ", ".join(missing))
    return ChangeMetadata(
        schema=values["schema"],
        change_id=values["id"],
        status=values["status"].casefold(),
    )


def merge_month_and_date(merged_at: str) -> tuple[str, str]:
    """把 GitHub merged_at 转为北京时间归档月份和日期。"""
    value = merged_at.strip()
    if not value:
        raise ArchiveChangeError("merged_at 不能为空")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArchiveChangeError(f"merged_at 不是合法 ISO-8601：{merged_at}") from exc
    if parsed.tzinfo is None:
        raise ArchiveChangeError("merged_at 必须携带时区")
    beijing = parsed.astimezone(BEIJING)
    return beijing.strftime("%Y-%m"), beijing.strftime("%Y-%m-%d")


def freeze_lifecycle(text: str, *, merged_date: str) -> str:
    """只把 ready_for_review/datetime 生命周期字段冻结为 done/merge date。"""
    lines = text.splitlines(keepends=True)
    plain = [line.rstrip("\r\n") for line in lines]
    _, end = _frontmatter_bounds(plain)
    status_seen = False
    updated_seen = False
    result = list(lines)

    for index in range(1, end):
        raw = plain[index]
        match = FRONTMATTER_FIELD_PATTERN.match(raw)
        if match is None:
            continue
        key = match.group("key")
        newline = "\n"
        if lines[index].endswith("\r\n"):
            newline = "\r\n"
        elif not lines[index].endswith(("\n", "\r\n")):
            newline = ""
        if key == "status":
            current = match.group("rest").strip().strip("\"'").casefold()
            if current != "ready_for_review":
                raise ArchiveChangeError(
                    f"自动归档只接受 status=ready_for_review；当前为 {current or '<empty>'}"
                )
            result[index] = f"status: done{newline}"
            status_seen = True
        elif key == "updated":
            result[index] = f"updated: {merged_date}{newline}"
            updated_seen = True

    if not status_seen or not updated_seen:
        missing = []
        if not status_seen:
            missing.append("status")
        if not updated_seen:
            missing.append("updated")
        raise ArchiveChangeError("Change 缺少可冻结生命周期字段：" + ", ".join(missing))

    frozen = "".join(result)
    _verify_lifecycle_only(text, frozen, merged_date=merged_date)
    return frozen


def _verify_lifecycle_only(original: str, frozen: str, *, merged_date: str) -> None:
    """证明归档内容只改变 status 和 updated 两个 frontmatter 字段。"""
    original_lines = original.splitlines()
    frozen_lines = frozen.splitlines()
    if len(original_lines) != len(frozen_lines):
        raise ArchiveChangeError("归档冻结不得改变 Change 行数")
    _, end = _frontmatter_bounds(original_lines)
    allowed_changed = {"status", "updated"}
    changed_keys: set[str] = set()
    for index, (before, after) in enumerate(zip(original_lines, frozen_lines, strict=True)):
        if before == after:
            continue
        if not 0 < index < end:
            raise ArchiveChangeError("归档冻结不得修改 frontmatter 之外的正文")
        before_match = FRONTMATTER_FIELD_PATTERN.match(before)
        after_match = FRONTMATTER_FIELD_PATTERN.match(after)
        if before_match is None or after_match is None:
            raise ArchiveChangeError("归档冻结出现非字段级 frontmatter 修改")
        key = before_match.group("key")
        if key != after_match.group("key") or key not in allowed_changed:
            raise ArchiveChangeError(f"归档冻结出现未授权字段修改：{key}")
        changed_keys.add(key)
    if changed_keys != allowed_changed:
        raise ArchiveChangeError(
            f"归档冻结必须且只能更新 status/updated；实际修改：{sorted(changed_keys)}"
        )
    if "status: done" not in frozen_lines:
        raise ArchiveChangeError("归档冻结结果缺少 status: done")
    if f"updated: {merged_date}" not in frozen_lines:
        raise ArchiveChangeError("归档冻结结果缺少 merge date updated")


def merged_source_at_revision(root: Path, *, revision: str, source_relative: str) -> str:
    """从 merged revision 读取原始 Active Change，并确认该 revision 仍属于当前 main 历史。"""
    revision = revision.strip()
    if not revision:
        raise ArchiveChangeError("merged revision 不能为空")

    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", revision, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if ancestor.returncode != 0:
        raise ArchiveChangeError(
            f"merged revision 不是当前 main HEAD 的祖先，无法确认归属：{revision}"
        )

    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{source_relative}"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise ArchiveChangeError(
            "merged revision 中不存在 PR 声明的 Active Change，无法确认归属："
            f"{revision}:{source_relative}"
        )
    return result.stdout


def archive_change(
    root: Path,
    *,
    changed_paths: Sequence[str],
    merged_at: str,
    expected_source: str | None = None,
) -> ArchiveResult:
    """按 merged PR changed files 归档唯一 Change，并绑定该 PR 的 merged revision 内容。"""
    root = root.resolve()
    selected = select_change(changed_paths)
    if selected is None:
        return ArchiveResult(
            changed=False,
            change_id=None,
            source=None,
            target=None,
            reason="not_applicable_no_active_change",
        )
    if expected_source is None:
        raise ArchiveChangeError("缺少 merged revision 的 Active Change 内容，无法确认归属")

    change_id, source_relative = selected
    month, merged_date = merge_month_and_date(merged_at)
    target_relative = f"changes/archive/{month}/{change_id}/CHANGE.md"
    source = root / source_relative
    target = root / target_relative

    if source.exists() and target.exists():
        raise ArchiveChangeError(
            f"同一 Change 同时存在 active/archive，拒绝猜测：{source_relative} / {target_relative}"
        )
    if not source.exists() and target.exists():
        archived_text = target.read_text(encoding="utf-8")
        metadata = parse_metadata(archived_text)
        if (
            metadata.schema != CURRENT_SCHEMA
            or metadata.change_id != change_id
            or metadata.status != "done"
        ):
            raise ArchiveChangeError("已存在 archive 与 expected current-schema/done 身份不一致")
        expected_archive = freeze_lifecycle(expected_source, merged_date=merged_date)
        if archived_text != expected_archive:
            raise ArchiveChangeError(
                "已存在 archive 与本 merged PR 的 Change 内容不一致，拒绝幂等猜测"
            )
        return ArchiveResult(
            changed=False,
            change_id=change_id,
            source=source_relative,
            target=target_relative,
            reason="already_archived",
        )
    if not source.exists():
        raise ArchiveChangeError(
            f"PR 声明携带 Active Change，但当前 main 上 active/archive 均不存在：{change_id}"
        )

    original = source.read_text(encoding="utf-8")
    if original != expected_source:
        raise ArchiveChangeError(
            "当前 main 上的 Active Change 已偏离本 merged PR 的版本，无法确认归属；"
            "停止归档并要求基于真实 main 状态处理"
        )
    metadata = parse_metadata(original)
    if metadata.schema != CURRENT_SCHEMA:
        raise ArchiveChangeError(f"自动归档只处理 {CURRENT_SCHEMA}，当前为 {metadata.schema}")
    if metadata.change_id != change_id:
        raise ArchiveChangeError(
            f"Change path ID 与 frontmatter id 不一致：{change_id} != {metadata.change_id}"
        )
    if metadata.status != "ready_for_review":
        raise ArchiveChangeError(f"自动归档只接受 ready_for_review，当前为 {metadata.status}")

    frozen = freeze_lifecycle(original, merged_date=merged_date)
    target.parent.mkdir(parents=True, exist_ok=False)
    target.write_text(frozen, encoding="utf-8")
    source.unlink()
    try:
        source.parent.rmdir()
        active_root = root / CHANGE_ROOT / "active"
        if active_root.is_dir() and not any(active_root.iterdir()):
            active_root.rmdir()
    except OSError:
        # 同目录存在其他合法文件/Change 时保持目录，不做递归清理。
        pass

    return ArchiveResult(
        changed=True,
        change_id=change_id,
        source=source_relative,
        target=target_relative,
        reason="archived",
    )


def _build_parser() -> argparse.ArgumentParser:
    """构造自动归档 CLI 参数。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--merged-at", required=True)
    parser.add_argument("--merged-revision", required=True)
    parser.add_argument("--changed-paths-file", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行自动归档并输出稳定 JSON；错误时 fail closed。"""
    arguments = _build_parser().parse_args(argv)
    root = Path(arguments.root).resolve()
    try:
        changed_paths = load_changed_paths(arguments.changed_paths_file)
        selected = select_change(changed_paths)
        expected_source = None
        if selected is not None:
            expected_source = merged_source_at_revision(
                root,
                revision=arguments.merged_revision,
                source_relative=selected[1],
            )
        result = archive_change(
            root,
            changed_paths=changed_paths,
            merged_at=arguments.merged_at,
            expected_source=expected_source,
        )
    except (ArchiveChangeError, OSError) as exc:
        print(f"CHANGE_ARCHIVE_ERROR: {exc}", file=sys.stderr)
        return 1

    payload = {"pr_number": arguments.pr_number, **result.as_dict()}
    if arguments.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "Change Archive："
            f"pr=#{arguments.pr_number} changed={str(result.changed).lower()} "
            f"change={result.change_id or '-'} reason={result.reason}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
