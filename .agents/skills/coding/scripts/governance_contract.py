#!/usr/bin/env python3
"""治理资产机器 Contract：校验 Coding Change、Issue/PR 实例与 GitHub governance projection。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Sequence


CHANGE_SCHEMA = "coding-change/v1"
CURRENT_CHANGE_ID_PATTERN = re.compile(
    r"^CHG-\d{8}-\d{6}-[a-z0-9]+(?:-[a-z0-9]+)*$"
)
LEGACY_CHANGE_ID_PATTERN = re.compile(
    r"^CHG-\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*$"
)
TOP_LEVEL_HEADING_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
SECOND_LEVEL_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
FRONTMATTER_FIELD_PATTERN = re.compile(r"^(?P<key>[a-z_]+):\s*(?P<value>.*?)\s*$")
ACCEPTANCE_ITEM_PATTERN = re.compile(
    r"^\s*-\s*\[(?P<checked>[ xX])\]\s*\*{0,2}AC(?P<number>[1-9][0-9]*)\*{0,2}[：:]\s*(?P<text>.+?)\s*$",
    re.MULTILINE,
)
CHECKED_TASK_PATTERN = re.compile(r"^\s*-\s*\[[xX]\]\s+\S.*$", re.MULTILINE)
ISSUE_HEADING_PATTERN = re.compile(r"^#{2,6}\s+(.+?)\s*$", re.MULTILINE)
FORM_TITLE_PATTERN = re.compile(r'^title:\s*"(?P<prefix>.+?)"\s*$', re.MULTILINE)
FORM_TYPE_PATTERN = re.compile(r"^\s*- type:\s*(?P<type>[a-z_]+)\s*$", re.MULTILINE)
FORM_ID_PATTERN = re.compile(r"^\s*id:\s*(?P<id>[a-z0-9_]+)\s*$", re.MULTILINE)
FORM_LABEL_PATTERN = re.compile(r"^\s*label:\s*(?P<label>.+?)\s*$", re.MULTILINE)
REQUIRED_HEADING_MARKER_PATTERN = re.compile(
    r"<!--\s*governance:required-for=(?P<level>L[23])\s*-->\s*\n"
    r"##\s+(?P<heading>.+?)\s*$",
    re.MULTILINE,
)
REQUIREMENT_SOURCE_PATTERN = re.compile(
    r"^Requirement-Source:\s*(?P<value>.*?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
INVALID_REQUIREMENT_SOURCE_VALUES = {"", "#<issue>", "tbd", "todo", "待确认", "无"}
ISSUE_FORM_CONFIG_NAME = "config.yml"
ISSUE_FORM_PROJECTION_RELATIVE = Path(".github/ISSUE_TEMPLATE")
PR_TEMPLATE_PROJECTION_RELATIVE = Path(".github/PULL_REQUEST_TEMPLATE.md")
CANONICAL_CODING_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CHANGE_TEMPLATE = CANONICAL_CODING_ROOT / "assets" / "CHANGE.template.md"
CANONICAL_ISSUE_FORM_DIR = CANONICAL_CODING_ROOT / "assets" / "issue-templates"
CANONICAL_PR_TEMPLATE = CANONICAL_CODING_ROOT / "assets" / "PULL_REQUEST_TEMPLATE.md"
VALID_ISSUE_MODES = {"create", "live", "closure"}
VALID_PR_MODES = {"create", "live"}


class GovernanceContractError(ValueError):
    """表示治理资产实例不满足当前机器 Contract。"""


class IssueProfile:
    """表示从 canonical GitHub Issue Form 恢复出的稳定机器 Profile。"""

    def __init__(
        self,
        filename: str,
        title_prefix: str,
        required_headings: tuple[str, ...],
        required_checkbox_headings: tuple[str, ...],
        required_textarea_headings: tuple[str, ...],
    ) -> None:
        """初始化当前治理 Profile 的稳定结构字段。"""
        self.filename = filename
        self.title_prefix = title_prefix
        self.required_headings = required_headings
        self.required_checkbox_headings = required_checkbox_headings
        self.required_textarea_headings = required_textarea_headings


class PullRequestProfile:
    """表示从 canonical PR Template 恢复出的有序 Core Profile。"""

    def __init__(self, required_headings: tuple[str, ...]) -> None:
        """初始化当前治理 Profile 的稳定结构字段。"""
        self.required_headings = required_headings


def _frontmatter_and_body(text: str) -> tuple[dict[str, str], str]:
    """解析扁平 Change frontmatter，并返回剩余 Markdown 正文。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise GovernanceContractError("Change 缺少 frontmatter 起始分隔符")
    metadata: dict[str, str] = {}
    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
        match = FRONTMATTER_FIELD_PATTERN.fullmatch(line.strip())
        if match is not None:
            metadata[match.group("key")] = match.group("value").strip().strip("\"'")
    if end_index is None:
        raise GovernanceContractError("Change frontmatter 未闭合")
    return metadata, "\n".join(lines[end_index + 1 :])


def template_top_level_headings(template_text: str) -> tuple[str, ...]:
    """从 canonical Change 模板提取有序一级标题。"""
    headings = tuple(match.group(1).strip() for match in TOP_LEVEL_HEADING_PATTERN.finditer(template_text))
    if not headings:
        raise GovernanceContractError("Change 模板未包含可识别的一级标题")
    if len(set(headings)) != len(headings):
        raise GovernanceContractError("Change 模板一级标题重复，无法形成稳定机器 Profile")
    return headings


def template_required_second_level_headings(template_text: str, level: str) -> tuple[str, ...]:
    """从模板 marker 恢复指定风险级别必需的二级标题。"""
    headings = tuple(
        match.group("heading").strip()
        for match in REQUIRED_HEADING_MARKER_PATTERN.finditer(template_text)
        if match.group("level") == level
    )
    if len(set(headings)) != len(headings):
        raise GovernanceContractError(f"Change 模板 {level} 必需二级标题重复")
    return headings


def _validate_ordered_headings(
    body: str,
    required_headings: Sequence[str],
    *,
    level: int,
    asset_name: str,
) -> list[str]:
    """校验 Markdown 必需标题完整、唯一且顺序正确。"""
    pattern = TOP_LEVEL_HEADING_PATTERN if level == 1 else SECOND_LEVEL_HEADING_PATTERN
    actual = [match.group(1).strip() for match in pattern.finditer(body)]
    errors: list[str] = []
    positions: list[int] = []
    for heading in required_headings:
        count = actual.count(heading)
        if count == 0:
            errors.append(f"{asset_name} 缺少必需标题：{heading}")
            continue
        if count > 1:
            errors.append(f"{asset_name} 必需标题重复：{heading}")
            continue
        positions.append(actual.index(heading))
    if len(positions) == len(required_headings) and positions != sorted(positions):
        errors.append(f"{asset_name} 必需标题顺序与当前 Profile 不一致")
    return errors


def is_current_change_id(change_id: str) -> bool:
    """判断 Change ID 是否符合当前秒级新建格式。"""
    return CURRENT_CHANGE_ID_PATTERN.fullmatch(change_id.strip()) is not None


def is_legacy_change_id(change_id: str) -> bool:
    """判断 Change ID 是否为只允许历史读取的日期级格式。"""
    candidate = change_id.strip()
    return (
        LEGACY_CHANGE_ID_PATTERN.fullmatch(candidate) is not None
        and CURRENT_CHANGE_ID_PATTERN.fullmatch(candidate) is None
    )


def validate_new_change_text(
    text: str,
    *,
    template_text: str,
    expected_id: str | None = None,
) -> list[str]:
    """校验新建或当前 changed Coding Change 的机器 Contract。"""
    try:
        metadata, body = _frontmatter_and_body(text)
        required_headings = template_top_level_headings(template_text)
        level = metadata.get("level", "")
        required_second_level = template_required_second_level_headings(template_text, level)
    except GovernanceContractError as exc:
        return [str(exc)]

    errors: list[str] = []
    schema = metadata.get("schema", "")
    change_id = metadata.get("id", "")
    if schema != CHANGE_SCHEMA:
        errors.append(f"新 Change schema 必须为 {CHANGE_SCHEMA}，当前为 {schema or '<empty>'}")
    if not is_current_change_id(change_id):
        errors.append(
            "新 Change ID 必须使用 CHG-YYYYMMDD-HHMMSS-kebab-case；日期级 ID 只保留历史读取兼容"
        )
    if expected_id is not None and change_id != expected_id:
        errors.append(f"Change frontmatter id 与目录身份不一致：{change_id!r} != {expected_id!r}")
    if level not in {"L2", "L3"}:
        errors.append(f"持久新 Change level 必须为 L2/L3，当前为 {level or '<empty>'}")
    errors.extend(
        _validate_ordered_headings(
            body,
            required_headings,
            level=1,
            asset_name="新 Change",
        )
    )
    if required_second_level:
        errors.extend(
            _validate_ordered_headings(
                body,
                required_second_level,
                level=2,
                asset_name=f"{level} Change",
            )
        )
    return errors


def validate_new_change_file(
    path: Path,
    *,
    template_path: Path = CANONICAL_CHANGE_TEMPLATE,
) -> list[str]:
    """读取 Change 与 canonical 模板并执行当前实例校验。"""
    expected_id = path.parent.name if path.name == "CHANGE.md" else None
    try:
        text = path.read_text(encoding="utf-8")
        template_text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"无法读取治理资产：{exc}"]
    return validate_new_change_text(
        text,
        template_text=template_text,
        expected_id=expected_id,
    )


def _normalise_issue_heading(value: str) -> str:
    """规范 Issue/PR Markdown 标题空白以稳定比较。"""
    return re.sub(r"\s+", " ", value.strip())


def _issue_headings(body: str) -> tuple[str, ...]:
    """提取 Issue 二到六级 Markdown 标题。"""
    return tuple(
        _normalise_issue_heading(match.group(1))
        for match in ISSUE_HEADING_PATTERN.finditer(body)
    )


def _form_blocks(text: str) -> tuple[str, ...]:
    """按 Issue Form 顶层 body item 切分 YAML 文本。"""
    starts = [match.start() for match in re.finditer(r"^  - type:\s*", text, re.MULTILINE)]
    if not starts:
        return ()
    starts.append(len(text))
    return tuple(text[starts[index] : starts[index + 1]] for index in range(len(starts) - 1))


def _field_is_required(block: str) -> bool:
    """判断当前 Issue Form 字段是否显式 required。"""
    lines = [line.strip() for line in block.splitlines()]
    try:
        validations_index = lines.index("validations:")
    except ValueError:
        return False
    return "required: true" in lines[validations_index + 1 :]


def load_issue_profile(path: Path) -> IssueProfile:
    """从 canonical Issue Form 动态恢复 creation/live Profile。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GovernanceContractError(f"无法读取 Issue Form {path}: {exc}") from exc
    title_match = FORM_TITLE_PATTERN.search(text)
    if title_match is None:
        raise GovernanceContractError(f"Issue Form {path} 缺少 title prefix")
    required_headings: list[str] = []
    required_checkbox_headings: list[str] = []
    required_textarea_headings: list[str] = []
    for block in _form_blocks(text):
        type_match = FORM_TYPE_PATTERN.search(block)
        field_id = FORM_ID_PATTERN.search(block)
        label = FORM_LABEL_PATTERN.search(block)
        if type_match is None or field_id is None or label is None or not _field_is_required(block):
            continue
        field_type = type_match.group("type")
        if field_type not in {"checkboxes", "textarea"}:
            continue
        heading = _normalise_issue_heading(label.group("label"))
        required_headings.append(heading)
        if field_type == "checkboxes":
            required_checkbox_headings.append(heading)
        else:
            required_textarea_headings.append(heading)
    if not required_headings:
        raise GovernanceContractError(f"Issue Form {path} 没有 required submission Profile")
    if len(set(required_headings)) != len(required_headings):
        raise GovernanceContractError(f"Issue Form {path} required labels 重复")
    return IssueProfile(
        filename=path.name,
        title_prefix=title_match.group("prefix"),
        required_headings=tuple(required_headings),
        required_checkbox_headings=tuple(required_checkbox_headings),
        required_textarea_headings=tuple(required_textarea_headings),
    )


def _canonical_issue_form_paths(forms_dir: Path) -> tuple[Path, ...]:
    """返回 canonical Issue Form 普通文件集合。"""
    if forms_dir.is_symlink() or not forms_dir.is_dir():
        raise GovernanceContractError(f"canonical Issue Form 目录不存在或非法：{forms_dir}")
    paths = tuple(
        sorted(
            path
            for path in forms_dir.glob("*.yml")
            if path.is_file() and not path.is_symlink()
        )
    )
    if not paths:
        raise GovernanceContractError(f"canonical Issue Form 目录为空：{forms_dir}")
    return paths


def load_issue_profiles(forms_dir: Path = CANONICAL_ISSUE_FORM_DIR) -> tuple[IssueProfile, ...]:
    """动态加载全部 canonical Issue 类型 Profile。"""
    profiles = tuple(
        load_issue_profile(path)
        for path in _canonical_issue_form_paths(forms_dir)
        if path.name != ISSUE_FORM_CONFIG_NAME
    )
    if not profiles:
        raise GovernanceContractError("canonical Issue Form 未定义任何 Requirement Source Profile")
    prefixes = [profile.title_prefix for profile in profiles]
    if len(set(prefixes)) != len(prefixes):
        raise GovernanceContractError("canonical Issue Form title prefix 重复，无法唯一解析类型")
    return profiles


def resolve_issue_profile(
    title: str,
    profile: str | None = None,
    *,
    forms_dir: Path = CANONICAL_ISSUE_FORM_DIR,
) -> IssueProfile:
    """按显式 profile 或 title prefix 解析唯一 Issue Profile。"""
    profiles = load_issue_profiles(forms_dir)
    if profile is not None:
        candidate = profile.strip().casefold().replace("_", "-")
        matches: list[IssueProfile] = []
        for current in profiles:
            stem = Path(current.filename).stem.casefold()
            suffix = stem.split("-", 1)[-1]
            title_identity = current.title_prefix.strip().strip("[]").strip().casefold()
            if candidate in {stem, suffix, title_identity}:
                matches.append(current)
        if len(matches) != 1:
            raise GovernanceContractError(f"未知或不唯一的 Issue Profile：{profile}")
        return matches[0]
    matches = [current for current in profiles if title.startswith(current.title_prefix)]
    if len(matches) != 1:
        allowed = " / ".join(current.title_prefix.strip() for current in profiles)
        raise GovernanceContractError(f"Issue 标题必须唯一匹配 canonical 类型前缀：{allowed}")
    return matches[0]


def _section_body(body: str, heading: str, pattern: re.Pattern[str]) -> str | None:
    """返回指定标题到下一标题之间的 section 正文。"""
    matches = list(pattern.finditer(body))
    target_index: int | None = None
    for index, match in enumerate(matches):
        if _normalise_issue_heading(match.group(1)) == heading:
            if target_index is not None:
                return None
            target_index = index
    if target_index is None:
        return None
    current = matches[target_index]
    start = current.end()
    end = matches[target_index + 1].start() if target_index + 1 < len(matches) else len(body)
    return body[start:end]


def _validate_strict_core(
    actual_headings: Sequence[str],
    required_headings: Sequence[str],
    *,
    asset_name: str,
) -> list[str]:
    """校验 creation Core 完整、唯一、严格顺序且无中间插入。"""
    errors: list[str] = []
    for heading in required_headings:
        count = actual_headings.count(heading)
        if count == 0:
            errors.append(f"{asset_name} 缺少必需语义段：{heading}")
        elif count > 1:
            errors.append(f"{asset_name} 必需语义段重复：{heading}")
    if errors:
        return errors
    last = actual_headings.index(required_headings[-1])
    actual_core = tuple(actual_headings[: last + 1])
    expected_core = tuple(required_headings)
    if actual_core != expected_core:
        errors.append(
            f"{asset_name} canonical Core 必须完整、唯一、严格顺序，且 Core 内不得插入自定义 section"
        )
    return errors


def _validate_live_headings(
    actual_headings: Sequence[str],
    required_headings: Sequence[str],
    *,
    asset_name: str,
) -> list[str]:
    """校验 live 实例仍包含全部历史兼容必需标题。"""
    errors: list[str] = []
    for heading in required_headings:
        count = actual_headings.count(heading)
        if count == 0:
            errors.append(f"{asset_name} 缺少必需语义段：{heading}")
        elif count > 1:
            errors.append(f"{asset_name} 必需语义段重复：{heading}")
    return errors


def validate_issue_instance(
    title: str,
    body: str,
    *,
    profile: str | None = None,
    mode: str = "live",
    require_all_checked: bool = False,
    forms_dir: Path = CANONICAL_ISSUE_FORM_DIR,
) -> list[str]:
    """校验 GitHub Requirement Source；create 严格 canonical Core，live/closure 兼容历史顺序。"""
    normalized_mode = mode.strip().casefold()
    if normalized_mode not in VALID_ISSUE_MODES:
        return [f"Issue validation mode 必须是 create/live/closure，当前为 {mode!r}"]
    errors: list[str] = []
    normalized_title = title.strip()
    try:
        contract = resolve_issue_profile(normalized_title, profile, forms_dir=forms_dir)
    except GovernanceContractError as exc:
        return [str(exc)]
    if not normalized_title.startswith(contract.title_prefix):
        errors.append(f"Issue 标题必须以 {contract.title_prefix!r} 开头")

    headings = _issue_headings(body)
    if normalized_mode == "create":
        errors.extend(_validate_strict_core(headings, contract.required_headings, asset_name="Issue"))
    else:
        # live/closure 保留 creation-time Contract 生效前的历史 Issue 兼容；只有 create 强制新增 checkbox Core。
        errors.extend(
            _validate_live_headings(headings, contract.required_textarea_headings, asset_name="Issue")
        )

    if normalized_mode == "create":
        for heading in contract.required_checkbox_headings:
            section = _section_body(body, heading, ISSUE_HEADING_PATTERN)
            if section is not None and CHECKED_TASK_PATTERN.search(section) is None:
                errors.append(f"Issue required checkbox section 未完成：{heading}")
        for heading in contract.required_textarea_headings:
            section = _section_body(body, heading, ISSUE_HEADING_PATTERN)
            if section is not None and not section.strip():
                errors.append(f"Issue required textarea section 不能为空：{heading}")

    acceptance = _section_body(body, "验收标准", ISSUE_HEADING_PATTERN)
    matches = list(ACCEPTANCE_ITEM_PATTERN.finditer(acceptance or ""))
    if not matches:
        errors.append("Issue 验收标准 section 必须包含 `- [ ] AC1：...` 形式的稳定 task list")
        return errors
    numbers = [int(match.group("number")) for match in matches]
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        errors.append(f"Issue Acceptance ID 必须从 AC1 连续且唯一，当前为 {numbers}")
    require_checked = require_all_checked or normalized_mode == "closure"
    for match in matches:
        if not match.group("text").strip():
            errors.append(f"AC{match.group('number')} 验收文本不能为空")
        if require_checked and match.group("checked").casefold() != "x":
            errors.append(f"AC{match.group('number')} 尚未勾选，不能完成 Requirement Source Closure")
    return errors


def load_pr_profile(template_path: Path = CANONICAL_PR_TEMPLATE) -> PullRequestProfile:
    """从 canonical PR Template 动态恢复有序 Core headings。"""
    try:
        text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GovernanceContractError(f"无法读取 canonical PR Template {template_path}: {exc}") from exc
    headings = tuple(match.group(1).strip() for match in SECOND_LEVEL_HEADING_PATTERN.finditer(text))
    if not headings:
        raise GovernanceContractError("canonical PR Template 未包含二级 Core headings")
    if len(set(headings)) != len(headings):
        raise GovernanceContractError("canonical PR Template Core heading 重复")
    return PullRequestProfile(required_headings=headings)


def _pr_section_body(body: str, heading: str) -> str | None:
    """返回 PR 指定二级标题 section 的正文。"""
    return _section_body(body, heading, SECOND_LEVEL_HEADING_PATTERN)


def validate_pr_instance(
    body: str,
    *,
    mode: str = "create",
    template_path: Path = CANONICAL_PR_TEMPLATE,
) -> list[str]:
    """校验 PR body；create 要求 canonical ordered Core，live 只做必要结构与 source shape 检查。"""
    normalized_mode = mode.strip().casefold()
    if normalized_mode not in VALID_PR_MODES:
        return [f"PR validation mode 必须是 create/live，当前为 {mode!r}"]
    try:
        profile = load_pr_profile(template_path)
    except GovernanceContractError as exc:
        return [str(exc)]
    headings = tuple(match.group(1).strip() for match in SECOND_LEVEL_HEADING_PATTERN.finditer(body))
    if normalized_mode == "create":
        errors = _validate_strict_core(headings, profile.required_headings, asset_name="PR")
    else:
        errors = _validate_live_headings(headings, profile.required_headings, asset_name="PR")

    source_section = _pr_section_body(body, "Requirement Source")
    if source_section is None:
        return errors
    sources = list(REQUIREMENT_SOURCE_PATTERN.finditer(source_section))
    if not sources:
        errors.append("PR Requirement Source section 至少需要一行 Requirement-Source:")
        return errors
    for match in sources:
        value = match.group("value").strip()
        if value.casefold() in INVALID_REQUIREMENT_SOURCE_VALUES:
            errors.append(f"PR Requirement-Source 不能使用占位值：{value or '<empty>'}")
    return errors


def validate_issue_form_projection(
    project_root: Path,
    *,
    forms_dir: Path = CANONICAL_ISSUE_FORM_DIR,
) -> list[str]:
    """校验根 Issue Forms 与 canonical assets 原字节一致。"""
    errors: list[str] = []
    target_dir = project_root / ISSUE_FORM_PROJECTION_RELATIVE
    try:
        canonical_paths = _canonical_issue_form_paths(forms_dir)
    except GovernanceContractError as exc:
        return [str(exc)]
    canonical_names = {source.name for source in canonical_paths}
    for source in canonical_paths:
        target = target_dir / source.name
        if not target.is_file() or target.is_symlink():
            errors.append(f"Issue Form 投影缺失或不是普通文件：{target}")
            continue
        try:
            if target.read_bytes() != source.read_bytes():
                errors.append(f"Issue Form 投影已漂移，必须从 canonical asset 重新生成：{target}")
        except OSError as exc:
            errors.append(f"无法读取 Issue Form 投影：{target}: {exc}")
    if target_dir.is_dir() and not target_dir.is_symlink():
        for target in sorted(target_dir.glob("*.yml")):
            if target.name not in canonical_names:
                errors.append(f"Issue Form 根投影包含非 canonical 文件：{target}")
    return errors


def validate_governance_projection(
    project_root: Path,
    *,
    forms_dir: Path = CANONICAL_ISSUE_FORM_DIR,
    pr_template: Path = CANONICAL_PR_TEMPLATE,
) -> list[str]:
    """校验根 Issue Forms 与 PR Template 全部 canonical projections。"""
    errors = validate_issue_form_projection(project_root, forms_dir=forms_dir)
    target = project_root / PR_TEMPLATE_PROJECTION_RELATIVE
    if not target.is_file() or target.is_symlink():
        errors.append(f"PR Template 投影缺失或不是普通文件：{target}")
    else:
        try:
            if target.read_bytes() != pr_template.read_bytes():
                errors.append(f"PR Template 投影已漂移，必须从 canonical asset 重新生成：{target}")
        except OSError as exc:
            errors.append(f"无法读取 PR Template 投影：{target}: {exc}")
    return errors


def _build_parser() -> argparse.ArgumentParser:
    """构建治理 Contract 的宿主无关 CLI 参数。"""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    change = subparsers.add_parser("validate-change", help="校验新 Coding Change 实例")
    change.add_argument("--path", type=Path, required=True)
    change.add_argument("--template", type=Path, default=CANONICAL_CHANGE_TEMPLATE)

    issue = subparsers.add_parser("validate-issue", help="校验 GitHub Requirement Source 实例")
    issue.add_argument("--title", required=True)
    issue.add_argument("--body-file", type=Path, required=True)
    issue.add_argument("--profile")
    issue.add_argument("--forms-dir", type=Path, default=CANONICAL_ISSUE_FORM_DIR)
    issue.add_argument("--mode", choices=sorted(VALID_ISSUE_MODES), default="live")
    issue.add_argument("--require-all-checked", action="store_true")
    issue.add_argument("--json", action="store_true")

    pull = subparsers.add_parser("validate-pr", help="校验 GitHub Pull Request body")
    pull.add_argument("--body-file", type=Path, required=True)
    pull.add_argument("--template", type=Path, default=CANONICAL_PR_TEMPLATE)
    pull.add_argument("--mode", choices=sorted(VALID_PR_MODES), default="create")
    pull.add_argument("--json", action="store_true")

    projection = subparsers.add_parser("validate-projection", help="校验根 GitHub Issue/PR governance projections")
    projection.add_argument("--root", type=Path, required=True)
    projection.add_argument("--forms-dir", type=Path, default=CANONICAL_ISSUE_FORM_DIR)
    projection.add_argument("--pr-template", type=Path, default=CANONICAL_PR_TEMPLATE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行治理资产机器 Contract CLI 并返回稳定退出码。"""
    args = _build_parser().parse_args(argv)
    json_output = bool(getattr(args, "json", False))
    if args.command == "validate-change":
        errors = validate_new_change_file(args.path, template_path=args.template)
    elif args.command == "validate-projection":
        errors = validate_governance_projection(
            args.root,
            forms_dir=args.forms_dir,
            pr_template=args.pr_template,
        )
    else:
        try:
            body = args.body_file.read_text(encoding="utf-8")
        except OSError as exc:
            label = "Issue" if args.command == "validate-issue" else "PR"
            errors = [f"无法读取 {label} body：{exc}"]
        else:
            if args.command == "validate-issue":
                errors = validate_issue_instance(
                    args.title,
                    body,
                    profile=args.profile,
                    mode=args.mode,
                    require_all_checked=args.require_all_checked,
                    forms_dir=args.forms_dir,
                )
            else:
                errors = validate_pr_instance(
                    body,
                    mode=args.mode,
                    template_path=args.template,
                )
    if json_output:
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    elif errors:
        for error in errors:
            print(f"GOVERNANCE_CONTRACT_ERROR: {error}", file=sys.stderr)
    else:
        print("治理资产机器 Contract 校验通过")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
