from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / ".github" / "workflows" / "change-archive.yml"
RUNTIME = ROOT / ".github" / "workflows" / "runtime.yml"
DOCS = ROOT / "docs" / "04_测试与调试说明.md"


def test_change_archive_only_auto_triggers_for_persistent_change_carrier() -> None:
    """没有持久 Change 的 merged PR 不应启动 Archive Runner，手工重跑入口仍保留。"""
    workflow = ARCHIVE.read_text(encoding="utf-8")
    assert "types: [closed]" in workflow
    assert 'paths: ["changes/active/**"]' in workflow
    assert "workflow_dispatch:" in workflow
    assert "pr_number:" in workflow
    assert "git push origin HEAD:main" in workflow


def test_runtime_required_context_keeps_existing_scope_fast_path() -> None:
    """Runtime required check 不用 path filter 消失，而是在无风险时快速成功。"""
    workflow = RUNTIME.read_text(encoding="utf-8")
    assert "name: Compose Golden Path" in workflow
    assert "Fast-path unchanged Runtime" in workflow
    assert "Detect Runtime risk changes" in workflow
    assert "Canonical Compose startup, security, persistence, and recovery" in workflow
    assert "paths:" not in workflow.split("permissions:", 1)[0]


def test_test_guide_still_describes_runtime_fast_path_without_copying_event_matrix() -> None:
    """正式测试文档保持长期职责事实；细粒度 event/cache 路由由 Workflow+回归持有。"""
    docs = DOCS.read_text(encoding="utf-8")
    assert "# 21. CI 怎么理解" in docs
    assert "`Compose Golden Path` 在每个 PR / main SHA 上保持存在" in docs
    assert "则快速成功，不重建整套 Runtime" in docs
    assert "最终判断必须用" in docs
    assert "PR 最新 HEAD" in docs
