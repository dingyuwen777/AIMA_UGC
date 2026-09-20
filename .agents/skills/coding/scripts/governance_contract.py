#!/usr/bin/env python3
"""治理资产机器 Contract：校验 Coding Change、Requirement Source 与 Issue Form 投影。"""

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
ISSUE_FORM_CONFIG_NAME = "config.yml"
ISSUE_FORM_PROJECTION_RELATIVE = Path(".github/ISSUE_TEMPLATE")
CANONICAL_CODING_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CHANGE_TEMPLATE = CANONICAL_CODING_ROOT / "assets" / "CHANGE.template.md"
CANONICAL_ISSUE_FORM_DIR = CANONICAL_CODING_ROOT / "assets" / "issue-templates"


class GovernanceContractError(ValueError):
    """表示治理资产实例不满足当前机器 Contract。"""


class IssueProfile:
    """表示从 canonical GitHub Issue Form 恢复出的稳定机器 Profile。"""

    def __init__(
        self,
        filename: str,
        title_prefix: str,
        required_headings: tuple[str, ...],
    ) -> None:
        """保存 Form 文件身份、标题前缀与 required textarea 语义段。"""
        self.filename = filename
        self.title_prefix = title_prefix
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
    """从 canonical Change 模板提取有序一级标题，避免 validator 维护第二份章节清单。"""
    headings = tuple(match.group(1).strip() for match in TOP_LEVEL_HEADING_PATTERN.finditer(template_text))
    if not headings:
        raise GovernanceContractError("Change 模板未包含可识别的一级标题")
    if len(set(headings)) != len(headings):
        raise GovernanceContractError("Change 模板一级标题重复，无法形成稳定机器 Profile")
    return headings


def template_required_second_level_headings(template_text: str, level: str) -> tuple[str, ...]:
    """从模板内显式 marker 恢复指定风险级别额外必需的二级标题。"""
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
    """校验 Markdown 标题完整、唯一且顺序与 Profile 一致。"""
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
    """判断 Change ID 是否符合当前新建实例的北京时间秒级格式。"""
    return CURRENT_CHANGE_ID_PATTERN.fullmatch(change_id.strip()) is not None


def is_legacy_change_id(change_id: str) -> bool:
    """判断 Change ID 是否为仅允许历史读取、且不与当前秒级格式重叠的日期级格式。"""
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
    """校验一个新建/当前 changed Coding Change 是否满足当前机器 Contract。"""
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
    """读取新 Change 与 canonical 模板并执行当前实例校验。"""
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
    """规范 GitHub Issue Markdown 标题，保留语义文本而忽略首尾空白。"""
    return re.sub(r"\s+", " ", value.strip())


def _issue_headings(body: str) -> tuple[str, ...]:
    """提取二到六级 Markdown 标题；Issue Form 与 API 写入可使用不同标题级别。"""
    return tuple(
        _normalise_issue_heading(match.group(1))
        for match in ISSUE_HEADING_PATTERN.finditer(body)
    )


def _form_blocks(text: str) -> tuple[str, ...]:
    """按 Issue Form 顶层 body item 切分 YAML 文本，避免增加 YAML 运行依赖。"""
    starts = [match.start() for match in re.finditer(r"^  - type:\s*", text, re.MULTILINE)]
    if not starts:
        return ()
    starts.append(len(text))
    return tuple(text[starts[index] : starts[index + 1]] for index in range(len(starts) - 1))


def _field_is_required(block: str) -> bool:
    """确认当前字段自己的 validations.required=true，避免其他控件误满足。"""
    lines = [line.strip() for line in block.splitlines()]
    try:
        validations_index = lines.index("validations:")
    except ValueError:
        return False
    return "required: true" in lines[validations_index + 1 :]


def load_issue_profile(path: Path) -> IssueProfile:
    """从一个 canonical Issue Form 恢复 title prefix 与 required textarea labels。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GovernanceContractError(f"无法读取 Issue Form {path}: {exc}") from exc
    title_match = FORM_TITLE_PATTERN.search(text)
    if title_match is None:
        raise GovernanceContractError(f"Issue Form {path} 缺少 title prefix")
    required_headings: list[str] = []
    for block in _form_blocks(text):
        type_match = FORM_TYPE_PATTERN.search(block)
        field_id = FORM_ID_PATTERN.search(block)
        label = FORM_LABEL_PATTERN.search(block)
        if type_match is None or type_match.group("type") != "textarea":
            continue
        if field_id is None or label is None or not _field_is_required(block):
            continue
        required_headings.append(_normalise_issue_heading(label.group("label")))
    if not required_headings:
        raise GovernanceContractError(f"Issue Form {path} 没有 required textarea Profile")
    if len(set(required_headings)) != len(required_headings):
        raise GovernanceContractError(f"Issue Form {path} required labels 重复")
    return IssueProfile(
        filename=path.name,
        title_prefix=title_match.group("prefix"),
        required_headings=tuple(required_headings),
    )


def _canonical_issue_form_paths(forms_dir: Path) -> tuple[Path, ...]:
    """返回 canonical Issue Form 资产；config 参与投影但不参与 Issue 类型 Profile。"""
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
    """从 canonical Issue Form assets 动态加载全部类型 Profile。"""
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
    """按显式 profile 或 canonical title prefix 解析唯一 Requirement Source 类型。"""
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


def validate_issue_instance(
    title: str,
    body: str,
    *,
    profile: str | None = None,
    require_all_checked: bool = False,
    forms_dir: Path = CANONICAL_ISSUE_FORM_DIR,
) -> list[str]:
    """校验 GitHub Requirement Source 实例的类型、语义段与稳定 Acceptance task list。"""
    errors: list[str] = []
    normalized_title = title.strip()
    try:
        contract = resolve_issue_profile(normalized_title, profile, forms_dir=forms_dir)
    except GovernanceContractError as exc:
        return [str(exc)]
    if not normalized_title.startswith(contract.title_prefix):
        errors.append(f"Issue 标题必须以 {contract.title_prefix!r} 开头")

    headings = _issue_headings(body)
    for heading in contract.required_headings:
        count = headings.count(heading)
        if count == 0:
            errors.append(f"Issue 缺少必需语义段：{heading}")
        elif count > 1:
            errors.append(f"Issue 必需语义段重复：{heading}")

    matches = list(ACCEPTANCE_ITEM_PATTERN.finditer(body))
    if not matches:
        errors.append("Issue 验收标准必须包含 `- [ ] AC1：...` 形式的稳定 task list")
        return errors
    numbers = [int(match.group("number")) for match in matches]
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        errors.append(f"Issue Acceptance ID 必须从 AC1 连续且唯一，当前为 {numbers}")
    for match in matches:
        if not match.group("text").strip():
            errors.append(f"AC{match.group('number')} 验收文本不能为空")
        if require_all_checked and match.group("checked").casefold() != "x":
            errors.append(f"AC{match.group('number')} 尚未勾选，不能完成 Requirement Source Closure")
    return errors


def validate_issue_form_projection(
    project_root: Path,
    *,
    forms_dir: Path = CANONICAL_ISSUE_FORM_DIR,
) -> list[str]:
    """校验仓库根 GitHub Issue Forms 是 canonical assets 的原字节受管投影。"""
    errors: list[str] = []
    target_dir = project_root / ISSUE_FORM_PROJECTION_RELATIVE
    try:
        canonical_paths = _canonical_issue_form_paths(forms_dir)
    except GovernanceContractError as exc:
        return [str(exc)]
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
    return errors


def _build_parser() -> argparse.ArgumentParser:
    """构建宿主无关 CLI，使无 Python import 集成的 Agent 也能调用同一校验器。"""
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
    issue.add_argument("--require-all-checked", action="store_true")
    issue.add_argument("--json", action="store_true")

    projection = subparsers.add_parser("validate-projection", help="校验根 GitHub Issue Forms 受管投影")
    projection.add_argument("--root", type=Path, required=True)
    projection.add_argument("--forms-dir", type=Path, default=CANONICAL_ISSUE_FORM_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行治理资产机器 Contract CLI，并用稳定退出码表达验证结果。"""
    args = _build_parser().parse_args(argv)
    if args.command == "validate-change":
        errors = validate_new_change_file(args.path, template_path=args.template)
    elif args.command == "validate-projection":
        errors = validate_issue_form_projection(args.root, forms_dir=args.forms_dir)
    else:
        try:
            body = args.body_file.read_text(encoding="utf-8")
        except OSError as exc:
            errors = [f"无法读取 Issue body：{exc}"]
        else:
            errors = validate_issue_instance(
                args.title,
                body,
                profile=args.profile,
                require_all_checked=args.require_all_checked,
                forms_dir=args.forms_dir,
            )
    if args.command == "validate-issue" and args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    elif errors:
        for error in errors:
            print(f"GOVERNANCE_CONTRACT_ERROR: {error}", file=sys.stderr)
    else:
        print("治理资产机器 Contract 校验通过")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
