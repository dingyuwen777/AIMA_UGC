import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
RUNTIME = ROOT / ".github" / "workflows" / "runtime.yml"
TOOLING = ROOT / ".github" / "workflows" / "tooling.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
FULLSTACK = ROOT / ".github" / "workflows" / "fullstack.yml"
LEGACY_COMPLETION = ROOT / ".github" / "workflows" / "change-completion-gate.yml"


def _section(text: str, start: str, end: str) -> str:
    """提取唯一 Workflow 文本区段，供结构回归限定断言范围。"""
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def test_pr_heavy_workflows_do_not_rerun_on_every_synchronize() -> None:
    """重 Workflow 只在 PR 生命周期边界运行，不跟随每次 push 自动重跑。"""
    for workflow in (CI, RUNTIME, TOOLING, RELEASE):
        trigger = workflow.read_text(encoding="utf-8").split("permissions:", 1)[0]
        assert "- synchronize" not in trigger
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
    assert text.count("Requirement Traceability and Completion Audit") == 1


def test_pr_body_edit_revalidates_metadata_without_overwriting_failed_full_evidence() -> None:
    """edited 只做 metadata，但必须绑定同 SHA 已成功的完整 CI/Runtime 基线。"""
    text = CI.read_text(encoding="utf-8")
    assert "- edited" in text
    assert "profile=metadata_only" in text
    assert "types:" in text
    assert "repository_required=false" in text
    assert "postgres_required=false" in text
    assert "fullstack_required=false" in text
    assert "Verify metadata edit baseline evidence" in text
    assert '"CI Gate"' in text
    assert '"Compose Golden Path"' in text
    assert "check-runs?per_page=100" in text
    assert "Metadata edit requires an already-green full evidence baseline" in text
    assert "github.event.action != 'edited'" in text


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
    assert job.index("Block Draft required evidence") < job.index("      - name: Checkout")
    assert "Canonical Compose startup, security, persistence, and recovery" in runtime


def test_runtime_required_check_keeps_cheap_unchanged_fast_path() -> None:
    """Ready/main 保持 Runtime fast-path；普通非 Runtime 改动不重建整套 Compose。"""
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "name: Compose Golden Path" in runtime
    assert "Detect Runtime risk changes" in runtime
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
    assert ci.count("runs-on: ubuntu-24.04") == 5
    assert "  actions-hygiene:" in ci
    hygiene = ci.split("  actions-hygiene:", 1)[1]
    assert "github.event_name == 'push'" in hygiene
    assert "github.ref == 'refs/heads/main'" in hygiene
    assert "needs: ci-gate" in hygiene
    assert runtime.count("runs-on: ubuntu-24.04") == 1
    assert "  quality-core:\n    name: Requirement Traceability and Completion Audit\n    if: always()\n    needs: ci-plan\n" in ci
    assert "Block Draft required evidence" in ci
    assert "Block Draft required evidence" in runtime
    assert "github.event.pull_request.draft == false" not in ci
    assert "github.event.pull_request.draft == false" not in runtime


def test_frontend_typechecks_once_through_build() -> None:
    """构建统一执行 TS 与 Vue 类型检查，CI 不重复支付相同验证成本。"""
    text = CI.read_text(encoding="utf-8")
    scripts = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))["scripts"]
    assert scripts["build"] == "npm run typecheck && vite build"
    assert scripts["typecheck"] == "npm run typecheck:ts7 && npm run typecheck:vue"
    assert text.count("npm --prefix frontend run build\n") == 1
    assert "npm --prefix frontend run typecheck\n" not in text


def test_backend_unit_suite_installs_cjk_font_prerequisite() -> None:
    """完整后端单测包含 Reporting 渲染，因此进入 backend suite 前必须准备 CJK 字体。"""
    text = CI.read_text(encoding="utf-8")
    assert (
        "      - name: Install report validation CJK font\n"
        "        if: needs.ci-plan.outputs.backend_required == 'true'\n" in text
    )
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
    assert "needs: main-evidence" in tooling
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
    assert "name: Linux Local Development Tooling" in linux
    assert "needs: main-evidence" in linux
    assert "runs-on: ubuntu-24.04" in linux
    assert "AIMA_DB_HOST: 127.0.0.1" in linux

    windows = tooling.split("  windows-tooling:\n", 1)[1]
    assert "name: Windows Development and Compose Tooling" in windows
    assert "needs: main-evidence" in windows
    assert "runs-on: windows-2025" in windows

    gate = _section(tooling, "  main-evidence:\n", "  linux-tooling:\n")
    assert gate.count("      - name: Checkout\n") == 1


def test_ci_plan_allows_core_postgres_and_fullstack_to_run_in_parallel() -> None:
    """轻量 CI Plan 只提供 scope，三个重 Evidence Owner 不再彼此串行等待。"""
    text = CI.read_text(encoding="utf-8")
    plan = _section(text, "  ci-plan:\n", "  quality-core:\n")
    core = _section(text, "  quality-core:\n", "  postgres-integration:\n")
    postgres = _section(text, "  postgres-integration:\n", "  real-fullstack:\n")
    fullstack = _section(text, "  real-fullstack:\n", "  ci-gate:\n")
    gate = _section(text, "  ci-gate:\n", "  actions-hygiene:\n")

    assert "name: CI Plan" in plan
    assert "Classify changed scope" in plan
    assert "needs: ci-plan" in core
    assert "needs: ci-plan" in postgres
    assert "needs: quality-core" not in postgres
    assert "needs: ci-plan" in fullstack
    assert "needs: quality-core" not in fullstack
    assert "      - ci-plan\n" in gate
    assert "      - quality-core\n" in gate
    assert "      - postgres-integration\n" in gate
    assert "      - real-fullstack\n" in gate
