import ast
import json
import os
import re
import runpy
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
RUNTIME = ROOT / ".github" / "workflows" / "runtime.yml"
TOOLING = ROOT / ".github" / "workflows" / "tooling.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
FULLSTACK = ROOT / ".github" / "workflows" / "fullstack.yml"
LEGACY_COMPLETION = ROOT / ".github" / "workflows" / "change-completion-gate.yml"


def test_review_tooling_metadata_skips_cannot_replace_formal_check_identities() -> None:
    text = TOOLING.read_text(encoding="utf-8")
    for name, identity in (
        ("linux-tooling", "Linux Local Development Tooling"),
        ("windows-tooling", "Windows Development and Compose Tooling"),
    ):
        declaration = text.split(f"  {name}:\n", 1)[1].split("    needs:", 1)[0]
        assert "github.event.action == 'edited' && !github.event.changes.base" in declaration
        assert f"'Metadata: {identity}'" in declaration
        assert f"|| '{identity}'" in declaration


def test_current_head_events_and_preflight_are_required_before_heavy_work() -> None:
    for workflow in (CI, RUNTIME, TOOLING, RELEASE):
        assert "- synchronize" in workflow.read_text(encoding="utf-8").split("permissions:", 1)[0]
    text = CI.read_text(encoding="utf-8")
    preflight = _section(text, "  preflight:\n", "  quality-core:\n")
    assert "Secret and docs gates" in preflight
    assert preflight.index("Secret and docs gates") < preflight.index(
        "Block Draft required evidence"
    )
    assert preflight.index("Validate template syntax before product setup") < preflight.index(
        "Block Draft required evidence"
    )
    assert preflight.index("Block Draft required evidence") < preflight.index(
        "Enforce changed PR Change readiness"
    )
    for name, end in (("postgres-integration", "real-fullstack"), ("real-fullstack", "ci-gate")):
        job = _section(text, f"  {name}:\n", f"  {end}:\n")
        assert "preflight" in job and "needs.preflight.result == 'success'" in job
    gate = _section(text, "  ci-gate:\n", "  actions-hygiene:\n")
    assert "PREFLIGHT_RESULT" in gate
    assert "github.event.changes.base" in text
    for workflow in (RUNTIME, TOOLING, RELEASE):
        source = workflow.read_text(encoding="utf-8")
        assert source.index(
            "Verify PR requirement and readiness before expensive validation"
        ) < source.index("Setup template validation Python")
        assert "check_pr_requirement_source.py" in source
        assert "check_change_completion.py --root . --changed-since" in source


def _section(text: str, start: str, end: str) -> str:
    """提取唯一 Workflow 文本区段，供结构回归限定断言范围。"""
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def test_pr_workflows_follow_current_head_without_running_draft_heavy_evidence() -> None:
    """每个新 HEAD 都有自动入口，Draft 成本由 job guard 控制。"""
    for workflow in (CI, RUNTIME, TOOLING, RELEASE):
        trigger = workflow.read_text(encoding="utf-8").split("permissions:", 1)[0]
        assert "- synchronize" in trigger
        assert "- opened" in trigger
        assert "- reopened" in trigger
        assert "- ready_for_review" in trigger


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
    assert text.count("    name: Requirement Traceability and Completion Audit") == 1


def test_pr_body_edit_revalidates_metadata_without_cancelling_full_evidence() -> None:
    """edited 使用独立 lane，并等待同 SHA full baseline，不能取消或冒充 Final CI。"""
    text = CI.read_text(encoding="utf-8")
    assert "- edited" in text
    assert "profile=metadata_only" in text
    assert "types:" in text
    assert "repository_required=false" in text
    assert "postgres_required=false" in text
    assert "fullstack_required=false" in text
    assert (
        "github.event.action == 'edited' && !github.event.changes.base && 'metadata' || 'full'"
        in text
    )
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text
    assert "Verify metadata edit baseline evidence" in text
    assert '--require "CI:CI Gate"' in text
    assert '--require "CI:Requirement Traceability and Completion Audit"' in text
    assert '--require "Runtime Acceptance:Compose Golden Path"' in text
    assert "scripts/quality/verify_pr_baseline.py" in text
    assert "base=${{ github.event.pull_request.base.sha || github.event.before }}" in text
    assert "merge=${{ github.sha }}" in text
    assert "sleep 5" in text
    assert "Timed out waiting for current HEAD/base/merge full evidence baseline." in text
    assert "github.event.action != 'edited'" in text


@pytest.mark.parametrize("change", ["base", "merge", "metadata", "skipped", "failure", "missing"])
def test_metadata_reuse_rejects_wrong_combination_and_incomplete_required_jobs(change: str) -> None:
    """旧 base、另一个 merge、metadata 和未完成正式身份均不能冒充基线。"""
    verify = runpy.run_path(str(ROOT / "scripts/quality/verify_pr_baseline.py"))["verify_baseline"]
    source = {
        "id": 1,
        "name": "CI",
        "event": "pull_request",
        "head_sha": "head",
        "display_title": "CI evidence head=head base=base merge=merge lane=full",
        "pull_requests": [{"head": {"sha": "head"}, "base": {"sha": "base"}}],
        "status": "completed",
        "conclusion": "success",
    }
    job = {"name": "CI Gate", "status": "completed", "conclusion": "success"}
    if change in {"base", "merge", "metadata"}:
        source["display_title"] = source["display_title"].replace(
            {"base": "base=base", "merge": "merge=merge", "metadata": "lane=full"}[change],
            "invalid",
        )
    elif change in {"failure", "skipped"}:
        job["conclusion"] = change
    with pytest.raises(ValueError):
        verify(
            [source],
            head="head",
            base="base",
            merge="merge",
            current_run=2,
            required={"CI": {"CI Gate"}},
            jobs=lambda _: [] if change == "missing" else [job],
        )


def test_metadata_reuse_waits_for_full_run_and_accepts_only_its_successful_identity() -> None:
    verify = runpy.run_path(str(ROOT / "scripts/quality/verify_pr_baseline.py"))["verify_baseline"]
    source = {
        "id": 1,
        "name": "CI",
        "event": "pull_request",
        "head_sha": "head",
        "display_title": "CI evidence head=head base=base merge=merge lane=full",
        "pull_requests": [{"head": {"sha": "head"}, "base": {"sha": "base"}}],
        "status": "in_progress",
        "conclusion": None,
    }
    arguments = {
        "head": "head",
        "base": "base",
        "merge": "merge",
        "current_run": 2,
        "required": {"CI": {"CI Gate"}},
        "jobs": lambda _: [{"name": "CI Gate", "status": "completed", "conclusion": "success"}],
    }
    assert verify([source], **arguments) == 75
    source.update(status="completed", conclusion="success")
    assert verify([source], **arguments) == 0
    latest = {**source, "id": 3, "conclusion": "failure"}
    with pytest.raises(ValueError):
        verify([source, latest], **arguments)


@pytest.mark.parametrize(
    "preflight,postgres,expected",
    [("failure", "skipped", 1), ("success", "skipped", 1), ("success", "success", 0)],
)
def test_actual_ci_gate_script_fails_closed_when_preflight_or_required_database_is_missing(
    preflight: str,
    postgres: str,
    expected: int,
) -> None:
    """执行正式 Gate 的 shell，而非只检查 YAML 包含某个字符串。"""
    git = shutil.which("git")
    windows_bash = Path(git).parents[1] / "bin/bash.exe" if git else Path("missing-bash")
    bash = (
        str(windows_bash)
        if windows_bash.is_file()
        else (shutil.which("bash") if os.name != "nt" else None)
    )
    if not bash:
        pytest.skip("Bash 不可用；Linux CI 必须执行此控制流回归")
    gate = _section(CI.read_text(encoding="utf-8"), "  ci-gate:\n", "  actions-hygiene:\n")
    script = textwrap.dedent(gate.split("        run: |\n", 1)[1])
    result = subprocess.run(
        [bash, "-c", script],
        capture_output=True,
        env={
            **os.environ,
            "PLAN_RESULT": "success",
            "PREFLIGHT_RESULT": preflight,
            "CORE_RESULT": "success",
            "POSTGRES_REQUIRED": "true",
            "POSTGRES_INTEGRATION_RESULT": postgres,
            "FULLSTACK_REQUIRED": "false",
            "FULLSTACK_RESULT": "skipped",
        },
    )
    assert result.returncode == expected


def test_draft_pr_required_checks_fail_closed_before_expensive_product_setup() -> None:
    """Draft 只运行轻量失败门禁，required contexts 不能以 skipped 状态满足合并。"""
    text = CI.read_text(encoding="utf-8")
    core = _section(text, "  quality-core:\n", "  postgres-integration:\n")
    gate = _section(text, "  ci-gate:\n", "  actions-hygiene:\n")

    assert "- ready_for_review" in text
    assert (
        "if: github.event_name != 'pull_request' || github.event.pull_request.draft == false"
        not in core
    )
    assert "      - name: Block Draft required evidence\n" in core
    assert "github.event.pull_request.draft == true" in core
    assert core.index("Block Draft required evidence") < core.index("      - name: Checkout")
    assert "  ci-gate:\n    name: CI Gate\n    if: always()\n" in gate
    assert "github.event.pull_request.draft == false" not in gate


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


def test_runtime_required_check_fails_closed_for_draft_then_reenters_on_ready() -> None:
    """Draft Runtime 只运行轻量失败门禁；Ready 后同一 HEAD 再取完整证据。"""
    runtime = RUNTIME.read_text(encoding="utf-8")
    job = runtime.split("  compose-golden-path:\n", 1)[1]

    assert "- ready_for_review" in runtime
    assert (
        "if: github.event_name != 'pull_request' || github.event.pull_request.draft == false"
        not in job
    )
    assert "      - name: Block Draft required evidence\n" in job
    assert "github.event.pull_request.draft == true" in job
    assert job.index("Lightweight source and template preflight") < job.index(
        "Block Draft required evidence"
    )
    assert job.index("Block Draft required evidence") < job.index("Prepare canonical Runtime env")
    assert "Canonical Compose startup, security, persistence, and recovery" in runtime


def test_runtime_required_check_keeps_cheap_unchanged_fast_path() -> None:
    """Ready/main 保持 Runtime fast-path；普通非 Runtime 改动不重建整套 Compose。"""
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "name: Compose Golden Path" in runtime
    assert "Classify shared Runtime responsibility" in runtime
    assert "scripts/quality/classify_ci_scope.py" in runtime
    assert "Fast-path unchanged Runtime" in runtime
    assert "No Runtime-relevant changes detected" in runtime
    assert "Canonical Compose startup, security, persistence, and recovery" in runtime


def test_tooling_skips_draft_jobs_and_reenters_on_ready_event() -> None:
    """Tooling 不是 required context；Draft 不启动昂贵 Linux/Windows Job，Ready 恢复原验证。"""
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
    """普通 Ready 保留产品证据 Runner；Hygiene 只在 main push 后占用维护 Runner。"""
    ci = CI.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert ci.count("runs-on: ubuntu-24.04") == 6
    assert "  actions-hygiene:" in ci
    hygiene = ci.split("  actions-hygiene:", 1)[1]
    assert "github.event_name == 'push'" in hygiene
    assert "github.ref == 'refs/heads/main'" in hygiene
    assert "needs: ci-gate" in hygiene
    assert runtime.count("runs-on: ubuntu-24.04") == 1
    assert (
        "  quality-core:\n"
        "    name: Requirement Traceability and Completion Audit\n"
        "    if: always()\n"
        "    needs: [ci-plan, preflight]\n" in ci
    )
    assert "Block Draft required evidence" in ci
    assert "Block Draft required evidence" in runtime
    core = _section(ci, "  quality-core:\n", "  postgres-integration:\n")
    assert "github.event.pull_request.draft == false" not in core
    runtime_header = runtime.split("  compose-golden-path:\n", 1)[1].split("    steps:", 1)[0]
    assert "github.event.pull_request.draft == false" not in runtime_header


def test_frontend_typechecks_once_through_build() -> None:
    """构建统一执行 TS 与 Vue 类型检查，CI 不重复支付相同验证成本。"""
    text = CI.read_text(encoding="utf-8")
    scripts = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))["scripts"]
    assert scripts["build"] == "npm run typecheck && vite build"
    assert scripts["typecheck"] == "npm run typecheck:ts7 && npm run typecheck:vue"
    assert text.count("npm --prefix frontend run build\n") == 1
    assert "npm --prefix frontend run typecheck\n" not in text


def test_backend_font_setup_only_runs_for_full_or_reporting_evidence() -> None:
    """精准 Backend target 不为无关 Reporting 测试支付字体安装成本。"""
    text = CI.read_text(encoding="utf-8")
    font_step = _section(
        text,
        "      - name: Install report validation CJK font\n",
        "      - name: Verify required runtime versions\n",
    )
    assert "needs.ci-plan.outputs.backend_targets == 'all'" in font_step
    assert "needs.ci-plan.outputs.report_font_required == 'true'" in font_step
    assert text.index("Install report validation CJK font") < text.index(
        "Unit, Contract and API tests"
    )


def test_main_push_reuses_same_tree_pr_evidence_without_changing_required_names() -> None:
    """main 只复用同 tree 且来源 check 绿色的 PR Evidence；required check identity 保持稳定。"""
    ci = CI.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")

    assert "Resolve reusable PR evidence on main" in ci
    assert "scripts/quality/resolve_main_evidence.py" in ci
    assert '--required-check "CI Gate"' in ci
    assert "profile=main_evidence_reuse" in ci
    assert "name: CI Gate" in ci

    assert "Resolve reusable Runtime evidence on main" in runtime
    assert '--required-check "Compose Golden Path"' in runtime
    assert "Reuse merged PR Runtime evidence" in runtime
    assert "name: Compose Golden Path" in runtime


def test_postgres_workflow_executes_exact_targets_before_domain_suites() -> None:
    """PostgreSQL job 支持精确 target，同时保留 suite/all 作为更宽风险的 fallback。"""
    ci = CI.read_text(encoding="utf-8")
    postgres_job = _section(ci, "  postgres-integration:\n", "  real-fullstack:\n")

    assert "POSTGRES_TARGETS" in postgres_job
    assert 'read -r -a targets <<< "${POSTGRES_TARGETS}"' in postgres_job
    assert 'uv run pytest "${targets[@]}" -q' in postgres_job
    assert "uv run pytest tests/integration/content -q" in postgres_job
    assert "uv run pytest tests/integration/ingestion -q" in postgres_job


def test_special_core_costs_are_conditioned_on_actual_inputs() -> None:
    """依赖审计与 Wheel 只在对应风险输入变化时运行，不再跟随所有前后端业务修改。"""
    ci = CI.read_text(encoding="utf-8")

    assert (
        "      - name: Audit frontend dependencies\n"
        "        if: needs.ci-plan.outputs.frontend_audit_required == 'true'\n" in ci
    )
    assert (
        "      - name: Build and verify Wheel\n"
        "        if: needs.ci-plan.outputs.package_required == 'true'\n" in ci
    )


def test_nightly_and_weekly_full_safety_nets_remain_available() -> None:
    """精准 PR 证据由低频全量 CI/Runtime/Tooling 回归提供安全网。"""
    ci = CI.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    tooling = TOOLING.read_text(encoding="utf-8")

    assert 'cron: "0 18 * * *"' in ci
    assert 'cron: "0 19 * * 0"' in runtime
    assert 'cron: "0 20 * * 0"' in tooling


def test_tooling_main_push_uses_lightweight_evidence_gate_before_os_jobs() -> None:
    """main 先在 Ubuntu 轻量核验 PR Tooling Evidence，同 tree 时不再启动 Linux/Windows 完整任务。"""
    tooling = TOOLING.read_text(encoding="utf-8")

    assert "  main-evidence:\n" in tooling
    assert "name: Reuse merged PR Tooling Evidence" in tooling
    assert '--required-check "Linux Local Development Tooling"' in tooling
    assert '--required-check "Windows Development and Compose Tooling"' in tooling
    assert "needs: [main-evidence, tooling-plan]" in tooling
    assert "needs.main-evidence.outputs.linux_reusable != 'true'" in tooling
    assert "needs.main-evidence.outputs.windows_reusable != 'true'" in tooling


def test_main_evidence_reuse_keeps_main_specific_cheap_governance_gates() -> None:
    """复用昂贵产品 Evidence 时仍保留 main 专属 Active Change 与仓库治理检查。"""
    ci = CI.read_text(encoding="utf-8")

    assert (
        "      - name: Enforce main Active Change readiness\n"
        "        if: github.event_name == 'push'\n" in ci
    )
    governance = _section(
        ci,
        "      - name: Verify AIMA project governance wiring\n",
        "      - name: Enforce changed PR Change readiness\n",
    )
    assert "steps.reuse.outputs.reusable" not in governance
    docs_gate = _section(
        ci,
        "      - name: Secret and docs gates\n",
        "      - name: Setup Python\n",
    )
    assert "steps.reuse.outputs.reusable" not in docs_gate


def test_ci_control_plane_compiles_before_project_python_setup() -> None:
    """main 复用控制面必须先被 Runner bootstrap Python 验证，而不是只依赖项目 Python。"""
    ci = CI.read_text(encoding="utf-8")

    compile_index = ci.index("Validate bootstrap-compatible CI control scripts")
    setup_index = ci.index("      - name: Setup Python")
    assert compile_index < setup_index
    compile_step = _section(
        ci,
        "      - name: Validate bootstrap-compatible CI control scripts\n",
        "      - name: Resolve reusable PR evidence on main\n",
    )
    assert "github.event_name != 'push'" in compile_step
    assert "python3 -m py_compile" in compile_step
    assert "scripts/quality/resolve_main_evidence.py" in ci
    assert "scripts/quality/classify_ci_scope.py" in ci
    for relative in (
        "scripts/quality/classify_ci_scope.py",
        "scripts/quality/check_env_templates.py",
        "scripts/quality/verify_pr_baseline.py",
        "scripts/dev/validate_changed.py",
    ):
        assert relative in compile_step
        ast.parse((ROOT / relative).read_text(encoding="utf-8"), feature_version=(3, 12))


def test_resolver_process_failure_falls_back_to_real_validation() -> None:
    """Resolver 自身失败只能关闭复用，不能让 CI/Runtime/Tooling 在控制面直接失败。"""
    ci = CI.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    tooling = TOOLING.read_text(encoding="utf-8")

    for workflow in (ci, runtime, tooling):
        assert "resolver_execution_failed" in workflow
        assert "reusable=false" in workflow
        assert "resolver_status" in workflow

    assert "main evidence resolver failed; falling back to real CI validation" in ci
    assert "Runtime evidence resolver failed; falling back to real Runtime validation" in runtime
    assert "Tooling evidence resolver failed; falling back to real Tooling validation" in tooling


def test_tooling_keeps_linux_and_windows_as_independent_jobs() -> None:
    """Evidence gate 不能吞掉 Linux/Windows job 边界，否则会静默丢失平台证据。"""
    tooling = TOOLING.read_text(encoding="utf-8")

    linux = _section(tooling, "  linux-tooling:\n", "  windows-tooling:\n")
    assert "|| 'Linux Local Development Tooling'" in linux
    assert "needs: [main-evidence, tooling-plan]" in linux
    assert "runs-on: ubuntu-24.04" in linux
    assert "AIMA_DB_HOST: 127.0.0.1" in linux

    windows = tooling.split("  windows-tooling:\n", 1)[1]
    assert "|| 'Windows Development and Compose Tooling'" in windows
    assert "needs: [main-evidence, tooling-plan]" in windows
    assert "runs-on: windows-2025" in windows

    gate = _section(tooling, "  main-evidence:\n", "  linux-tooling:\n")
    assert gate.count("      - name: Checkout\n") == 1


def test_preflight_allows_core_postgres_and_fullstack_to_run_in_parallel_after_success() -> None:
    """轻量失败先阻断，成功后三个独立重层并行，不等待产品 Core。"""
    text = CI.read_text(encoding="utf-8")
    plan = _section(text, "  ci-plan:\n", "  quality-core:\n")
    core = _section(text, "  quality-core:\n", "  postgres-integration:\n")
    postgres = _section(text, "  postgres-integration:\n", "  real-fullstack:\n")
    fullstack = _section(text, "  real-fullstack:\n", "  ci-gate:\n")
    gate = _section(text, "  ci-gate:\n", "  actions-hygiene:\n")

    assert "name: CI Plan" in plan
    assert "Classify changed scope" in plan
    assert "if: always()" in core
    assert "Block failed CI Plan" in core
    assert "PLAN_RESULT: ${{ needs.ci-plan.result }}" in gate
    assert 'test "${PLAN_RESULT}" = "success"' in gate
    assert "needs: [ci-plan, preflight]" in core
    assert "needs: [ci-plan, preflight]" in postgres
    assert "needs.preflight.result == 'success'" in postgres
    assert "needs: quality-core" not in postgres
    assert "github.event.pull_request.draft == false" in postgres
    assert "needs: [ci-plan, preflight]" in fullstack
    assert "needs.preflight.result == 'success'" in fullstack
    assert "needs: quality-core" not in fullstack
    assert "github.event.pull_request.draft == false" in fullstack
    assert "      - ci-plan\n" in gate
    assert "      - quality-core\n" in gate
    assert "      - postgres-integration\n" in gate
    assert "      - real-fullstack\n" in gate


def test_core_consumes_selected_backend_and_frontend_targets_from_ci_plan() -> None:
    """Core 的 Targeted Evidence 只消费 Plan 输出，不重新计算 changed scope。"""
    text = CI.read_text(encoding="utf-8")
    core = _section(text, "  quality-core:\n", "  postgres-integration:\n")
    assert "BACKEND_TARGETS: ${{ needs.ci-plan.outputs.backend_targets }}" in core
    assert "FRONTEND_UNIT_TARGETS: ${{ needs.ci-plan.outputs.frontend_unit_targets }}" in core
    assert "FRONTEND_E2E_SPECS: ${{ needs.ci-plan.outputs.frontend_e2e_specs }}" in core
    assert "scripts/quality/classify_ci_scope.py" not in core
    # npm exec 的 prefix 不改变工作目录；必须复用 script 加载前端配置。
    assert 'npm --prefix frontend run test -- --run "${unit_targets[@]}"' in core
    assert 'npm --prefix frontend run test:e2e -- "${e2e_specs[@]}"' in core


def test_targeted_backend_does_not_pay_global_api_suite() -> None:
    """Backend targeted profile 只运行 classifier targets；全量 API 仅属于 all fallback。"""
    text = CI.read_text(encoding="utf-8")
    core = _section(text, "  quality-core:\n", "  postgres-integration:\n")
    step = _section(
        core,
        "      - name: Unit, Contract and API tests\n",
        "      - name: Architecture and ownership gates\n",
    )
    all_branch = step.split('if [[ " ${BACKEND_TARGETS} " == *" all "* ]]; then', 1)[1].split(
        'elif [[ -n "${BACKEND_TARGETS}" ]]; then', 1
    )[0]
    targeted_branch = step.split('elif [[ -n "${BACKEND_TARGETS}" ]]; then', 1)[1].split("else", 1)[
        0
    ]
    assert "uv run pytest tests/api -q" in all_branch
    assert "uv run pytest tests/api -q" not in targeted_branch
    assert 'uv run pytest "${targets[@]}" -q' in targeted_branch


@pytest.mark.parametrize(
    ("paths", "python_required"),
    [
        (("frontend/package-lock.json",), True),
        (("frontend/src/shared/ui/AimaMultiSelect.vue",), True),
        (("frontend/tests/analysis-labels-editor.spec.ts",), True),
        (("frontend/src/features/voice-plaza/store.ts",), True),
        (("backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py",), True),
        (("scripts/quality/check_docs.py",), True),
        (("docs/product/README.md",), False),
        (("changes/active/CHG-example/CHANGE.md",), False),
    ],
)
def test_selected_product_tests_receive_locked_python_prerequisites(
    paths: tuple[str, ...], python_required: bool
) -> None:
    """前端会调用正式 Prompt 解析器，所选产品测试必须获得同一锁定环境。"""
    classify = runpy.run_path(str(ROOT / "scripts/quality/classify_ci_scope.py"))[
        "classify_requirements"
    ]
    requirements = classify(paths)
    text = CI.read_text(encoding="utf-8")
    core = _section(text, "  quality-core:\n", "  postgres-integration:\n")
    for name in (
        "Setup Python",
        "Cache uv downloads",
        "Verify required runtime versions",
        "Install frozen Python environment",
    ):
        step = core.split(f"      - name: {name}\n", 1)[1].split("      - name:", 1)[0]
        selector = (
            step.split("PYTHON_REQUIRED:", 1)[1].split("\n", 1)[0]
            if (name == "Verify required runtime versions")
            else step.split("if:", 1)[1].split("uses:", 1)[0].split("shell:", 1)[0]
        )
        flags = re.findall(r"needs\.ci-plan\.outputs\.(\w+) == 'true'", selector)
        assert flags, name
        enabled = any(getattr(requirements, flag) for flag in flags)
        assert enabled is python_required, (paths, name, flags)

    installation = core.split("      - name: Install frozen Python environment\n", 1)[1]
    installation = installation.split("      - name:", 1)[0]
    assert "uv lock --check" in installation
    assert "uv sync --locked" in installation
    assert 'uv run python -c "import aima_ugc"' in installation
    assert core.index("Install frozen Python environment") < core.index(
        "Frontend unit, build and Browser Mock Acceptance"
    )
