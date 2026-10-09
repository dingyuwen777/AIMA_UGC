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


def test_runtime_draft_required_check_fails_closed_then_ready_uses_changed_scope() -> None:
    """Draft 只支付轻量失败门禁；Ready/main 继续按 changed-scope 取得 Runtime 证据。"""
    workflow = RUNTIME.read_text(encoding="utf-8")
    job = workflow.split("  compose-golden-path:\n", 1)[1]

    assert "name: Compose Golden Path" in workflow
    assert "- ready_for_review" in workflow
    assert "      - name: Block Draft required evidence\n" in job
    assert "github.event.pull_request.draft == true" in job
    assert job.index("Lightweight source and template preflight") < job.index(
        "Block Draft required evidence"
    )
    assert job.index("Block Draft required evidence") < job.index(
        "Setup template validation Python"
    )
    assert (
        "if: github.event_name != 'pull_request' || github.event.pull_request.draft == false"
        not in job
    )
    assert "Fast-path unchanged Runtime" in workflow
    assert "Classify shared Runtime responsibility" in workflow
    assert "scripts/quality/classify_ci_scope.py" in workflow
    assert "steps.scope.outputs.runtime_required == 'true'" in workflow
    assert "Canonical Compose startup, security, persistence, and recovery" in workflow
    assert "paths:" not in workflow.split("permissions:", 1)[0]
