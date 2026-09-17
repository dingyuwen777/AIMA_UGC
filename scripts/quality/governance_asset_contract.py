"""AIMA 项目治理资产机器 Contract：从项目 Profile 与受管模板恢复稳定机器约束。"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
ISSUE_TEMPLATE_DIR = Path(".github/ISSUE_TEMPLATE")
CHANGE_TEMPLATE = Path(".agents/skills/coding/assets/CHANGE.template.md")
CURRENT_CHANGE_ID_PATTERN = re.compile(
    r"^CHG-\d{8}-\d{6}-[a-z0-9]+(?:-[a-z0-9]+)*$"
)
FRONTMATTER_FIELD_PATTERN = re.compile(r"^(?P<key>[a-z_]+):\s*(?P<value>.*?)\s*$")
TOP_LEVEL_HEADING_PATTERN = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
SECOND_LEVEL_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
ISSUE_HEADING_PATTERN = re.compile(r"^#{2,6}\s+(.+?)\s*$", re.MULTILINE)
ACCEPTANCE_ITEM_PATTERN = re.compile(
    r"^\s*-\s*\[(?P<checked>[ xX])\]\s*\*{0,2}AC(?P<number>[1-9][0-9]*)\*{0,2}[：:]\s*(?P<text>.+?)\s*$",
    re.MULTILINE,
)
FORM_TITLE_PATTERN = re.compile(r'^title:\s*"(?P<prefix>.+?)"\s*$', re.MULTILINE)
FORM_TYPE_PATTERN = re.compile(r"^\s*- type:\s*(?P<type>[a-z_]+)\s*$", re.MULTILINE)
FORM_ID_PATTERN = re.compile(r"^\s*id:\s*(?P<id>[a-z0-9_]+)\s*$", re.MULTILINE)
FORM_LABEL_PATTERN = re.compile(r"^\s*label:\s*(?P<label>.+?)\s*$", re.MULTILINE)
ISSUE_FORM_FILES = (
    "01-requirement.yml",
    "02-bug.yml",
    "03-technical-change.yml",
)
L3_REQUIRED_SECOND_LEVEL_HEADINGS = ("备选方案与取舍",)


class GovernanceAssetContractError(ValueError):
    """表示 AIMA 治理资产不满足当前项目机器 Contract。"""


@dataclass(frozen=True)
class IssueProfile:
    """表示从 GitHub Issue Form 恢复出的项目机器 Profile。"""

    filename: str
    title_prefix: str
    required_headings: tuple[str, ...]


def _normalise_heading(value: str) -> str:
    """规范 Markdown / Issue Form label 的空白，不改变语义文本。"""
    return re.sub(r"\s+", " ", value.strip())


def _form_blocks(text: str) -> tuple[str, ...]:
    """按 Issue Form 顶层 body item 切分 YAML 文本，避免引入 YAML 运行依赖。"""
    starts = [match.start() for match in re.finditer(r"^  - type:\s*", text, re.MULTILINE)]
    if not starts:
        return ()
    starts.append(len(text))
    return tuple(text[starts[index] : starts[index + 1]] for index in range(len(starts) - 1))


def load_issue_profile(path: Path) -> IssueProfile:
    """从项目 Issue Form 的 title 与 required textarea labels 恢复机器 Profile。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GovernanceAssetContractError(f"无法读取 Issue Form {path}: {exc}") from exc
    title_match = FORM_TITLE_PATTERN.search(text)
    if title_match is None:
        raise GovernanceAssetContractError(f"Issue Form {path} 缺少 title prefix")

    required_headings: list[str] = []
    for block in _form_blocks(text):
        type_match = FORM_TYPE_PATTERN.search(block)
        field_id = FORM_ID_PATTERN.search(block)
        label = FORM_LABEL_PATTERN.search(block)
        if type_match is None or type_match.group("type") != "textarea":
            continue
        if field_id is None or label is None or "required: true" not in block:
            continue
        required_headings.append(_normalise_heading(label.group("label")))
    if not required_headings:
        raise GovernanceAssetContractError(f"Issue Form {path} 没有 required textarea Profile")
    if len(set(required_headings)) != len(required_headings):
        raise GovernanceAssetContractError(f"Issue Form {path} required labels 重复")
    return IssueProfile(
        filename=path.name,
        title_prefix=title_match.group("prefix"),
        required_headings=tuple(required_headings),
    )


def load_issue_profiles(root: Path = ROOT) -> tuple[IssueProfile, ...]:
    """加载 AIMA 三类 Issue Form Profile，并保持文件顺序稳定。"""
    return tuple(
        load_issue_profile(root / ISSUE_TEMPLATE_DIR / filename)
        for filename in ISSUE_FORM_FILES
    )


def _resolve_issue_profile(title: str, profiles: Sequence[IssueProfile]) -> IssueProfile:
    """使用项目真实 title prefix 选择唯一 Issue Profile。"""
    matches = [profile for profile in profiles if title.startswith(profile.title_prefix)]
    if len(matches) != 1:
        raise GovernanceAssetContractError(
            "Issue 标题必须唯一匹配项目 [需求] / [缺陷] / [技术变更] Profile"
        )
    return matches[0]


def validate_issue_instance(
    title: str,
    body: str,
    *,
    root: Path = ROOT,
    require_all_checked: bool = False,
) -> list[str]:
    """校验 live GitHub Requirement Source 是否满足当前 AIMA Project Profile。"""
    try:
        profile = _resolve_issue_profile(title.strip(), load_issue_profiles(root))
    except GovernanceAssetContractError as exc:
        return [str(exc)]

    headings = tuple(_normalise_heading(match.group(1)) for match in ISSUE_HEADING_PATTERN.finditer(body))
    errors: list[str] = []
    for required in profile.required_headings:
        count = headings.count(required)
        if count == 0:
            errors.append(f"Issue 缺少项目 Profile 必需语义段：{required}")
        elif count > 1:
            errors.append(f"Issue 项目 Profile 必需语义段重复：{required}")

    acceptance = list(ACCEPTANCE_ITEM_PATTERN.finditer(body))
    if not acceptance:
        errors.append("Issue 验收标准必须包含 `- [ ] AC1：...` 形式的稳定 task list")
        return errors
    numbers = [int(match.group("number")) for match in acceptance]
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        errors.append(f"Issue Acceptance ID 必须从 AC1 连续且唯一，当前为 {numbers}")
    for match in acceptance:
        if require_all_checked and match.group("checked").casefold() != "x":
            errors.append(f"AC{match.group('number')} 尚未勾选，不能完成 Requirement Source Closure")
    return errors


def _frontmatter_and_body(text: str) -> tuple[dict[str, str], str]:
    """解析 Coding Change 的扁平 frontmatter 与 Markdown 正文。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise GovernanceAssetContractError("Change 缺少 frontmatter")
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
        raise GovernanceAssetContractError("Change frontmatter 未闭合")
    return metadata, "\n".join(lines[end_index + 1 :])


def _template_headings(template_text: str) -> tuple[str, ...]:
    """从当前受管 Change 模板动态恢复有序一级 Profile。"""
    headings = tuple(match.group(1).strip() for match in TOP_LEVEL_HEADING_PATTERN.finditer(template_text))
    if not headings or len(set(headings)) != len(headings):
        raise GovernanceAssetContractError("当前受管 Change 模板一级 Profile 不可解析")
    return headings


def _validate_ordered_headings(body: str, required: Sequence[str], *, level: int) -> list[str]:
    """校验 Change 必需标题存在、唯一且顺序稳定。"""
    pattern = TOP_LEVEL_HEADING_PATTERN if level == 1 else SECOND_LEVEL_HEADING_PATTERN
    actual = [match.group(1).strip() for match in pattern.finditer(body)]
    errors: list[str] = []
    positions: list[int] = []
    for heading in required:
        count = actual.count(heading)
        if count == 0:
            errors.append(f"新 Change 缺少必需标题：{heading}")
            continue
        if count > 1:
            errors.append(f"新 Change 必需标题重复：{heading}")
            continue
        positions.append(actual.index(heading))
    if len(positions) == len(required) and positions != sorted(positions):
        errors.append("新 Change 必需标题顺序与当前受管 Profile 不一致")
    return errors


def validate_new_change_file(path: Path, *, root: Path = ROOT) -> list[str]:
    """校验本 PR 新增 Coding Change 的 current identity 与当前受管模板 Profile。"""
    try:
        text = path.read_text(encoding="utf-8")
        template_text = (root / CHANGE_TEMPLATE).read_text(encoding="utf-8")
        metadata, body = _frontmatter_and_body(text)
        required_headings = _template_headings(template_text)
    except (OSError, GovernanceAssetContractError) as exc:
        return [str(exc)]

    errors: list[str] = []
    change_id = metadata.get("id", "")
    if metadata.get("schema") != "coding-change/v1":
        errors.append("新 Change schema 必须为 coding-change/v1")
    if CURRENT_CHANGE_ID_PATTERN.fullmatch(change_id) is None:
        errors.append(
            "新 Change ID 必须使用 CHG-YYYYMMDD-HHMMSS-kebab-case；日期级 ID 只保留历史 archive 兼容"
        )
    if path.name == "CHANGE.md" and path.parent.name != change_id:
        errors.append("Change 目录 ID 与 frontmatter id 不一致")
    level = metadata.get("level", "")
    if level not in {"L2", "L3"}:
        errors.append(f"持久新 Change level 必须为 L2/L3，当前为 {level or '<empty>'}")
    errors.extend(_validate_ordered_headings(body, required_headings, level=1))
    if level == "L3":
        errors.extend(_validate_ordered_headings(body, L3_REQUIRED_SECOND_LEVEL_HEADINGS, level=2))
    return errors


def _added_change_paths(root: Path, base_sha: str, head_sha: str) -> tuple[Path, ...]:
    """只枚举 PR base→head 新增的 AIMA 顶层 Active Change，避免回溯历史 archive。"""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--name-only",
            "--diff-filter=A",
            "--no-renames",
            base_sha,
            head_sha,
            "--",
            "changes/active",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise GovernanceAssetContractError(
            "无法计算本 PR 新增 Change 范围：" + result.stderr.strip()
        )
    return tuple(Path(line.strip()) for line in result.stdout.splitlines() if line.strip())


def validate_new_changes_since(root: Path, *, base_sha: str, head_sha: str) -> tuple[str, ...]:
    """对本 PR 新增 Change 执行 current machine Contract；历史 archive 不参与。"""
    validated: list[str] = []
    errors: list[str] = []
    for relative in _added_change_paths(root, base_sha, head_sha):
        parts = relative.parts
        if len(parts) != 4 or parts[:2] != ("changes", "active") or relative.name != "CHANGE.md":
            continue
        document_errors = validate_new_change_file(root / relative, root=root)
        if document_errors:
            errors.append(
                f"新增 Change `{relative.as_posix()}` 不满足当前 Project Profile：\n- "
                + "\n- ".join(document_errors)
            )
        else:
            validated.append(relative.as_posix())
    if errors:
        raise GovernanceAssetContractError("\n".join(errors))
    return tuple(validated)
