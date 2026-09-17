from __future__ import annotations

import runpy
import shutil
import subprocess
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "scripts" / "quality" / "governance_asset_contract.py"
CONTRACT = runpy.run_path(str(CONTRACT_PATH))
LOAD_ISSUE_PROFILES = CONTRACT["load_issue_profiles"]
VALIDATE_ISSUE_INSTANCE = CONTRACT["validate_issue_instance"]
VALIDATE_NEW_CHANGE_FILE = CONTRACT["validate_new_change_file"]
VALIDATE_NEW_CHANGES_SINCE = CONTRACT["validate_new_changes_since"]


def _prepare_root(tmp_path: Path) -> Path:
    """复制 Project Profile 与当前受管 Change 模板到临时仓库。"""
    issue_target = tmp_path / ".github" / "ISSUE_TEMPLATE"
    issue_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / ".github" / "ISSUE_TEMPLATE", issue_target)
    template_target = tmp_path / ".agents" / "skills" / "coding" / "assets"
    template_target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT / ".agents" / "skills" / "coding" / "assets" / "CHANGE.template.md",
        template_target / "CHANGE.template.md",
    )
    return tmp_path


def _git(root: Path, *arguments: str) -> str:
    """在临时仓库执行确定性 Git 操作并返回 stdout。"""
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _technical_issue_body() -> str:
    """构造满足当前技术变更 Issue Form required labels 的最小实例。"""
    return """## 动机 / 根因
统一治理资产机器语义。

## 当前状态
不同宿主存在漂移窗口。

## 目标状态
所有写入路径受同一门禁约束。

## 范围
- 治理资产。

## 非目标
- 不改业务行为。

## 兼容与迁移
历史资产保持不变。

## 风险与回滚
失败时 revert。

## 验收标准
- [ ] AC1：新治理资产必须通过机器门禁。
- [ ] AC2：历史治理资产不被批量改写。

## 验证要求
- 项目治理回归。

## 上游事实源 / 相关资料
- 项目规则。
"""


def _write_change(root: Path, change_id: str, *, level: str = "L3") -> Path:
    """用当前受管模板生成测试 Change，使 Profile 来源保持单一。"""
    raw = (root / ".agents/skills/coding/assets/CHANGE.template.md").read_text(encoding="utf-8")
    content = Template(raw).safe_substitute(
        change_id=change_id,
        title="治理资产测试",
        level=level,
        owner="test",
        branch="test/governance-contract",
        created="2026-09-17T15:30:00+08:00",
        updated="2026-09-17T15:30:00+08:00",
        depends_on="[]",
        affected_areas="[governance]",
        affected_paths="[scripts/quality]",
        contracts="[coding-change/v1]",
        data_changes="[]",
    )
    path = root / "changes" / "active" / change_id / "CHANGE.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_project_issue_profiles_are_recovered_from_forms(tmp_path: Path) -> None:
    """Project Profile 必须直接来自三类 Issue Form，而不是在 checker 复制第二份字段表。"""
    root = _prepare_root(tmp_path)
    profiles = LOAD_ISSUE_PROFILES(root)
    assert tuple(profile.title_prefix for profile in profiles) == (
        "[需求] ",
        "[缺陷] ",
        "[技术变更] ",
    )
    technical = profiles[2]
    assert "动机 / 根因" in technical.required_headings
    assert "验收标准" in technical.required_headings
    assert "验证要求" in technical.required_headings


def test_live_issue_instance_uses_project_profile_and_stable_acceptance(tmp_path: Path) -> None:
    """API/网页创建的 live Issue 也必须满足当前项目 Form 的机器语义。"""
    root = _prepare_root(tmp_path)
    assert (
        VALIDATE_ISSUE_INSTANCE(
            "[技术变更] 统一治理",
            _technical_issue_body(),
            root=root,
        )
        == []
    )


def test_live_issue_rejects_non_contiguous_acceptance_ids(tmp_path: Path) -> None:
    """Acceptance 必须连续稳定，不能用 AC1/AC3 或普通列表冒充最终状态 Owner。"""
    root = _prepare_root(tmp_path)
    body = _technical_issue_body().replace("AC2：", "AC3：")
    errors = VALIDATE_ISSUE_INSTANCE("[技术变更] 统一治理", body, root=root)
    assert any("连续且唯一" in error for error in errors)


def test_new_change_uses_second_precision_identity_and_current_template(tmp_path: Path) -> None:
    """新 Change 的 current ID 与结构必须由当前受管模板共同约束。"""
    root = _prepare_root(tmp_path)
    path = _write_change(root, "CHG-20260917-153000-machine-contract")
    assert VALIDATE_NEW_CHANGE_FILE(path, root=root) == []


def test_new_change_rejects_date_only_identity_without_touching_history(tmp_path: Path) -> None:
    """date-only 身份不能作为本 PR 新实例；该断言不扫描或迁移历史 archive。"""
    root = _prepare_root(tmp_path)
    path = _write_change(root, "CHG-20260917-machine-contract")
    errors = VALIDATE_NEW_CHANGE_FILE(path, root=root)
    assert any("HHMMSS" in error for error in errors)


def test_l3_change_cannot_drop_tradeoff_structure(tmp_path: Path) -> None:
    """L3 必须保留方案取舍入口，即使结论是不适用也不能删除结构。"""
    root = _prepare_root(tmp_path)
    path = _write_change(root, "CHG-20260917-153001-l3-contract")
    content = path.read_text(encoding="utf-8").replace("## 备选方案与取舍", "## 其他说明")
    path.write_text(content, encoding="utf-8")
    errors = VALIDATE_NEW_CHANGE_FILE(path, root=root)
    assert any("备选方案与取舍" in error for error in errors)


def test_changed_existing_active_change_is_revalidated(tmp_path: Path) -> None:
    """已有 current Active Change 被另一个宿主改坏时，PR changed-scope 仍必须重新校验。"""
    root = _prepare_root(tmp_path)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "governance-contract")
    _git(root, "config", "user.email", "governance-contract@example.invalid")
    path = _write_change(root, "CHG-20260917-153002-existing-contract")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "建立治理资产基线")
    base = _git(root, "rev-parse", "HEAD")

    broken = path.read_text(encoding="utf-8").replace("# 完成审计", "# 其他审计")
    path.write_text(broken, encoding="utf-8")
    _git(root, "add", str(path.relative_to(root)))
    _git(root, "commit", "-m", "模拟宿主破坏治理结构")
    head = _git(root, "rev-parse", "HEAD")

    try:
        VALIDATE_NEW_CHANGES_SINCE(root, base_sha=base, head_sha=head)
    except CONTRACT["GovernanceAssetContractError"] as exc:
        assert "完成审计" in str(exc)
    else:
        raise AssertionError("已修改 Active Change 未被 current machine Contract 拒绝")


def test_history_archive_is_outside_current_change_revalidation(tmp_path: Path) -> None:
    """历史 archive 即使是 date-only identity，也不进入本 PR Active Change current Profile 扫描。"""
    root = _prepare_root(tmp_path)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "governance-contract")
    _git(root, "config", "user.email", "governance-contract@example.invalid")
    archive = root / "changes/archive/2026-09/CHG-20260916-legacy/CHANGE.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("legacy immutable history\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "建立历史归档基线")
    base = _git(root, "rev-parse", "HEAD")
    archive.write_text("legacy immutable history touched for fixture\n", encoding="utf-8")
    _git(root, "add", str(archive.relative_to(root)))
    _git(root, "commit", "-m", "模拟历史路径变化")
    head = _git(root, "rev-parse", "HEAD")

    assert VALIDATE_NEW_CHANGES_SINCE(root, base_sha=base, head_sha=head) == ()
