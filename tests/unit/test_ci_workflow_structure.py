from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
RUNTIME = ROOT / ".github" / "workflows" / "runtime.yml"
TOOLING = ROOT / ".github" / "workflows" / "tooling.yml"
FULLSTACK = ROOT / ".github" / "workflows" / "fullstack.yml"
LEGACY_COMPLETION = ROOT / ".github" / "workflows" / "change-completion-gate.yml"


def test_ci_consolidates_ubuntu_core_without_losing_required_contexts() -> None:
    """统一 Core 必须承接 Scope/Governance/Completion/Repository Quality 责任。"""
    text = CI.read_text(encoding="utf-8")
    assert "name: Requirement Traceability and Completion Audit" in text
    assert "name: CI Gate" in text
    assert "name: CI Scope" not in text
    assert "name: Docs and Governance" not in text
    assert "name: Repository Quality" not in text
    assert "Verify PR Requirement Source" in text
    assert "Enforce changed PR Change readiness" in text
    assert "Secret and docs gates" in text
    assert "Unit, Contract and API tests" in text
    assert "Frontend unit, build and Browser Mock Acceptance" in text
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text


def test_completion_workflow_is_removed_after_evidence_moves_into_core() -> None:
    """旧独立 Completion Workflow 不得在责任迁移后作为重复 Owner 继续存在。"""
    assert not LEGACY_COMPLETION.exists()
    text = CI.read_text(encoding="utf-8")
    assert text.count("Requirement Traceability and Completion Audit") == 1


def test_pr_body_edit_revalidates_metadata_without_overwriting_failed_full_evidence() -> None:
    """edited 只做 metadata，但必须绑定同 SHA 已成功的完整 CI/Runtime 基线。"""
    text = CI.read_text(encoding="utf-8")
    assert "- edited" in text
    assert "profile=metadata_only" in text
    assert "Verify metadata edit baseline evidence" in text
    assert '"CI Gate"' in text
    assert '"Compose Golden Path"' in text
    assert "check-runs?per_page=100" in text
    assert "Metadata edit requires an already-green full evidence baseline" in text
    assert "github.event.action != 'edited'" in text


def test_draft_pr_is_fail_closed_before_expensive_product_setup() -> None:
    """Draft 只验证追溯并明确失败；Ready event 会重新运行完整 profile。"""
    text = CI.read_text(encoding="utf-8")
    assert "- ready_for_review" in text
    assert "Defer full CI while PR is Draft" in text
    assert "github.event.pull_request.draft" in text
    assert "mark it Ready for review" in text
    assert text.index("Defer full CI while PR is Draft") < text.index("Setup Python")
    assert text.index("Verify PR Requirement Source") < text.index("Defer full CI while PR is Draft")


def test_frontend_audit_runs_once_at_the_same_high_threshold() -> None:
    """前端依赖审计只保留一次完整 high 阈值检查。"""
    text = CI.read_text(encoding="utf-8")
    assert text.count("npm --prefix frontend audit --audit-level=high") == 1
    assert "npm --prefix frontend audit --omit=dev --audit-level=high" not in text


def test_expensive_independent_evidence_keeps_its_owner() -> None:
    """PostgreSQL、Real Full-stack 与 Compose Runtime 必须继续保留独立证明 Owner。"""
    text = CI.read_text(encoding="utf-8")
    assert "name: PostgreSQL Integration" in text
    assert "name: Real Full-stack Golden Path" in text
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "name: Compose Golden Path" in runtime
    assert "Canonical Compose startup, security, persistence, and recovery" in runtime


def test_runtime_required_check_keeps_cheap_unchanged_fast_path() -> None:
    """Compose Golden Path 是 required context；普通改动继续用现有 runner 内 fast-path，避免缺失 check。"""
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "name: Compose Golden Path" in runtime
    assert "Detect Runtime risk changes" in runtime
    assert "Fast-path unchanged Runtime" in runtime
    assert "No Runtime-relevant changes detected" in runtime
    assert "Canonical Compose startup, security, persistence, and recovery" in runtime


def test_tooling_skips_draft_jobs_and_reenters_on_ready_event() -> None:
    tooling = TOOLING.read_text(encoding="utf-8")
    assert "- ready_for_review" in tooling
    assert tooling.count("github.event.pull_request.draft == false") >= 2
    assert "Linux Local Development Tooling" in tooling
    assert "Windows Development and Compose Tooling" in tooling


def test_dependency_caches_only_cover_package_downloads() -> None:
    """缓存只优化依赖下载，不缓存测试或产品构建产物。"""
    ci = CI.read_text(encoding="utf-8")
    fullstack = FULLSTACK.read_text(encoding="utf-8")
    tooling = TOOLING.read_text(encoding="utf-8")
    for text in (ci, fullstack, tooling):
        assert "cache: npm" in text or "Cache uv downloads" in text
    combined = "\n".join((ci, fullstack, tooling))
    assert ".runtime-dist" not in combined
    assert "dist/**" not in combined


def test_daily_code_pr_runner_budget_keeps_independent_owners_but_avoids_draft_heavy_jobs() -> None:
    """普通 Ready 仍保留独立证据 Owner；Draft 不预付产品/Tooling/Release 重工作。"""
    ci = CI.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert ci.count("runs-on: ubuntu-24.04") == 3
    assert runtime.count("runs-on: ubuntu-24.04") == 1
    assert "needs: quality-core" in ci
    assert "Defer full CI while PR is Draft" in ci
    assert "Fast-path unchanged Runtime" in runtime
