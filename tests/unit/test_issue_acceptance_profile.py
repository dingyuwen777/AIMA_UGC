from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_TEST = runpy.run_path(str(ROOT / "tests/unit/test_agent_governance.py"))
CHECK_REPOSITORY = GOVERNANCE_TEST["CHECK_REPOSITORY"]
MINIMAL_REPOSITORY = GOVERNANCE_TEST["_minimal_repository"]

FORM_PROFILES = {
    "01-requirement.yml": ("需求", "[需求] "),
    "02-bug.yml": ("缺陷", "[缺陷] "),
    "03-technical-change.yml": ("技术变更", "[技术变更] "),
}


def _field_block(text: str, field_id: str) -> str:
    """返回 Issue Form 指定字段块，便于锁定公共字段语义。"""
    marker = f"id: {field_id}"
    assert marker in text
    tail = text.split(marker, 1)[1]
    next_field = tail.find("\n  - type:")
    return tail if next_field < 0 else tail[:next_field]


def test_current_issue_profiles_share_title_acceptance_and_validation_contract() -> None:
    """AIMA 三类 GitHub Issue Form 应共享标题、AC 与验证要求公共 Contract。"""
    for filename, (chooser_name, title_prefix) in FORM_PROFILES.items():
        text = (ROOT / ".github/ISSUE_TEMPLATE" / filename).read_text(encoding="utf-8")
        first_lines = text.splitlines()[:4]
        assert f"name: {chooser_name}" in first_lines
        assert f'title: "{title_prefix}"' in first_lines

        acceptance = _field_block(text, "acceptance_criteria")
        validation = _field_block(text, "validation_requirements")
        assert "label: 验收标准" in acceptance
        assert "- [ ] AC1：" in acceptance
        assert "required: true" in acceptance
        assert "label: 验证要求" in validation
        assert "required: true" in validation


def test_current_pr_template_delays_auto_close_when_post_merge_evidence_is_required() -> None:
    """需要 main-fresh 等 merge 后证据时，PR 不得提前自动关闭 Requirement Source。"""
    text = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    for marker in (
        "需要 post-merge evidence",
        "不得使用 `Closes` / `Fixes` / `Resolves`",
        "Closure Audit",
        "Requirement-Source:",
    ):
        assert marker in text


def test_checker_rejects_issue_profile_contract_drift(tmp_path: Path) -> None:
    """项目 checker 必须把 chooser/title/AC/validation 漂移变成稳定失败。"""
    MINIMAL_REPOSITORY(tmp_path)
    errors = CHECK_REPOSITORY(tmp_path)
    assert any(error.startswith("GOV017") for error in errors)


def test_checker_rejects_missing_post_merge_closure_contract(tmp_path: Path) -> None:
    """项目 checker 必须阻止 PR Template 丢失 post-merge Closure 时序。"""
    MINIMAL_REPOSITORY(tmp_path)
    errors = CHECK_REPOSITORY(tmp_path)
    assert any(
        error.startswith("GOV014") and "post-merge" in error
        for error in errors
    )
