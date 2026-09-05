from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / ".github" / "workflows" / "change-archive.yml"
RUNTIME = ROOT / ".github" / "workflows" / "runtime.yml"


def test_change_archive_only_auto_triggers_for_persistent_change_carrier() -> None:
    """没有持久 Change 的 merged PR 不应启动 Archive Runner，手工重跑入口仍保留。"""
    workflow = ARCHIVE.read_text(encoding="utf-8")
    assert "types: [closed]" in workflow
    assert 'paths: ["changes/active/**"]' in workflow
    assert "workflow_dispatch:" in workflow
    assert "pr_number:" in workflow
    assert "git push origin HEAD:main" in workflow


def test_runtime_required_context_is_draft_fail_closed_then_ready_scoped() -> None:
    """Draft 不预付 Compose；Ready/main 继续按 changed-scope 取得 Runtime 证据。"""
    workflow = RUNTIME.read_text(encoding="utf-8")
    assert "name: Compose Golden Path" in workflow
    assert "- ready_for_review" in workflow
    assert "Defer Runtime Acceptance while PR is Draft" in workflow
    assert "Fast-path unchanged Runtime" in workflow
    assert "Detect Runtime risk changes" in workflow
    assert "Canonical Compose startup, security, persistence, and recovery" in workflow
    assert "paths:" not in workflow.split("permissions:", 1)[0]
