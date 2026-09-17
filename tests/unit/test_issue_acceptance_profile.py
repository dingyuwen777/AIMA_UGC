from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_TEST = runpy.run_path(str(ROOT / "tests/unit/test_agent_governance.py"))
CHECK_REPOSITORY = GOVERNANCE_TEST["CHECK_REPOSITORY"]
MINIMAL_REPOSITORY = GOVERNANCE_TEST["_minimal_repository"]


def test_current_issue_forms_are_generated_projection() -> None:
    """AIMA 根 Issue Forms 必须与受管 canonical assets 原字节一致。"""
    source_dir = ROOT / ".agents/skills/coding/assets/issue-templates"
    target_dir = ROOT / ".github/ISSUE_TEMPLATE"
    sources = tuple(sorted(source_dir.glob("*.yml")))
    assert sources
    assert {path.name for path in sources} == {
        path.name for path in target_dir.glob("*.yml")
    }
    for source in sources:
        assert (target_dir / source.name).read_bytes() == source.read_bytes()


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


def test_checker_rejects_issue_projection_drift(tmp_path: Path) -> None:
    """AIMA 项目 checker 必须把根 Issue Form 漂移变成稳定失败。"""
    MINIMAL_REPOSITORY(tmp_path)
    form = tmp_path / ".github/ISSUE_TEMPLATE/03-technical-change.yml"
    form.write_text(form.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    errors = CHECK_REPOSITORY(tmp_path)
    assert any(error.startswith("GOV012") and "投影" in error for error in errors)


def test_checker_rejects_missing_post_merge_closure_contract(tmp_path: Path) -> None:
    """项目 checker 必须阻止 PR Template 丢失 post-merge Closure 时序。"""
    MINIMAL_REPOSITORY(tmp_path)
    errors = CHECK_REPOSITORY(tmp_path)
    assert any(error.startswith("GOV014") and "post-merge" in error for error in errors)
