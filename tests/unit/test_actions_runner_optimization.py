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


def test_runtime_required_context_is_draft_fail_closed_then_ready_scoped() -> None:
    """Draft 不预付 Compose 重工作；Ready/main 继续按 Runtime changed-scope 取得 required context。"""
    workflow = RUNTIME.read_text(encoding="utf-8")
    assert "name: Compose Golden Path" in workflow
    assert "- ready_for_review" in workflow
    assert "Defer Runtime Acceptance while PR is Draft" in workflow
    assert "Fast-path unchanged Runtime" in workflow
    assert "Detect Runtime risk changes" in workflow
    assert "Canonical Compose startup, security, persistence, and recovery" in workflow
    assert "paths:" not in workflow.split("permissions:", 1)[0]


def test_test_guide_describes_draft_ready_metadata_and_archive_cost_controls() -> None:
    """正式测试文档必须解释当前 Runner 优化边界，不能把 fast-path 写成降低测试标准。"""
    docs = DOCS.read_text(encoding="utf-8")
    assert "# 21. CI 怎么理解" in docs
    assert "Draft PR" in docs
    assert "PR body edited" in docs
    assert "同一 HEAD 已经存在成功的 CI Gate + Compose Golden Path 基线" in docs
    assert "Draft 阶段快速失败且不 checkout/构建 Compose" in docs
    assert "只对 merged PR 中实际修改 `changes/active/**`" in docs
    assert "Dependency cache 只允许缓存 package manager 的下载内容" in docs
    assert "PR 最新 HEAD" in docs
