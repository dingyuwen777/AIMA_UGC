from __future__ import annotations

import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = runpy.run_path(str(ROOT / "scripts" / "quality" / "classify_ci_scope.py"))
CLASSIFY_REQUIREMENTS = SCRIPT["classify_requirements"]
WRITE_GITHUB_OUTPUT = SCRIPT["_write_github_output"]
FULLSTACK_ALL = SCRIPT["FULLSTACK_ALL"]
POSTGRES_ALL = SCRIPT["POSTGRES_ALL"]


def test_review_runtime_artifacts_keep_real_consumers() -> None:
    """镜像内 Nginx 配置必须保留真实容器与离线镜像证据。"""
    nginx = CLASSIFY_REQUIREMENTS(["frontend/nginx.conf"])
    assert nginx.runtime_required and nginx.release_required
    assert not nginx.tooling_linux_required and not nginx.tooling_windows_required
    assert "COPY frontend/nginx.conf /etc/nginx/nginx.conf" in (ROOT / "Dockerfile").read_text(
        encoding="utf-8"
    )
    runtime = (ROOT / ".github/workflows/runtime.yml").read_text(encoding="utf-8")
    assert "steps.scope.outputs.runtime_required == 'true'" in runtime
    assert "compose up -d --build --wait" in runtime
    for path in (*SCRIPT["RUNTIME_EXACT"], *SCRIPT["LINUX_SOURCE_BOOTSTRAP_EXACT"]):
        assert (ROOT / path).is_file(), path


def test_review_source_bootstrap_keeps_linux_provider_consumer() -> None:
    system = CLASSIFY_REQUIREMENTS(["backend/src/aima_ugc/adapters/persistence/postgres/system.py"])
    assert system.tooling_linux_required
    assert not system.tooling_windows_required


def test_review_usage_is_controlled_docs_only_without_blanket_markdown_exemption() -> None:
    assert CLASSIFY_REQUIREMENTS(["USAGE.md"]).profile == "docs_only"
    assert CLASSIFY_REQUIREMENTS(["unknown-root.md"]).profile == "full"


def test_review_target_availability_uses_resolved_merge_checkout_not_pr_head(
    tmp_path: Path,
) -> None:
    """三点范围来自 PR，执行目标必须来自已经解决冲突的实际 merge checkout。"""

    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(tmp_path), *arguments]).decode().strip()

    git("init", "-b", "main")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Fixture")
    relative = "tests/unit/analysis/test_analysis_scheme_compilation.py"
    leaf = tmp_path / relative
    leaf.parent.mkdir(parents=True)
    leaf.write_text("# original\n")
    git("add", ".")
    git("commit", "-m", "base")
    git("checkout", "-b", "feature")
    leaf.unlink()
    git("add", ".")
    git("commit", "-m", "feature deletes leaf")
    head = git("rev-parse", "HEAD")
    git("checkout", "main")
    leaf.write_text("# main changes leaf\n")
    git("add", ".")
    git("commit", "-m", "main advances")
    base = git("rev-parse", "HEAD")
    conflict = subprocess.run(
        ["git", "-C", str(tmp_path), "merge", "--no-commit", head], capture_output=True
    )
    assert conflict.returncode == 1
    leaf.write_text("# resolved merge retains leaf\n")
    git("add", ".")
    git("commit", "-m", "resolve merge")
    result, changed = SCRIPT["classify_scope"](base, head, root=tmp_path)
    assert changed == [relative]
    assert result.backend_targets == (relative,)


@pytest.mark.parametrize("mode", ["unstaged_delete", "committed_rename"])
@pytest.mark.parametrize(
    "path,field,expected",
    [
        (
            "tests/unit/analysis/test_analysis_scheme_compilation.py",
            "backend_targets",
            ("tests/unit/analysis",),
        ),
        ("frontend/tests/voice-plaza.spec.ts", "frontend_unit_targets", ("all",)),
        ("frontend/e2e/voice-plaza.spec.ts", "frontend_e2e_specs", ("all",)),
        ("tests/integration/content/test_workbench_runtime.py", "postgres_suites", ("content",)),
        ("frontend/e2e-fullstack/analysis-streaming.spec.ts", "fullstack_specs", ("all",)),
    ],
)
def test_review_missing_targets_use_actual_checkout_owner_not_process_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    path: str,
    field: str,
    expected: tuple[str, ...],
) -> None:
    """保留删除/改名的风险，同时只按目标 checkout 选择仍能执行的 Owner 责任。"""

    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(tmp_path), *arguments]).decode().strip()

    git("init", "-b", "main")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Fixture")
    original = tmp_path / path
    original.parent.mkdir(parents=True)
    original.write_text("# old test\n")
    survivor = original.with_name(
        "test_survivor.py" if path.endswith(".py") else "survivor.spec.ts"
    )
    survivor.write_text("# current owner\n")
    git("add", ".")
    git("commit", "-m", "base")
    git("branch", "base")
    if mode == "committed_rename":
        original.rename(original.with_name("renamed_" + original.name))
        git("add", ".")
        git("commit", "-m", "rename test")
    else:
        original.unlink()
    monkeypatch.chdir(ROOT)
    assert (ROOT / path).exists()
    result, changed = SCRIPT["classify_scope"](
        "base", "HEAD", root=tmp_path, include_worktree=mode == "unstaged_delete"
    )
    assert path in changed
    assert getattr(result, field) == expected
    assert path not in (
        *result.backend_targets,
        *result.frontend_unit_targets,
        *result.frontend_e2e_specs,
        *result.postgres_targets,
    )
    if path.startswith("tests/integration/"):
        assert result.postgres_required and not result.postgres_targets
    elif path.startswith("frontend/e2e-fullstack/"):
        assert result.fullstack_required
    local = runpy.run_path(str(ROOT / "scripts/dev/validate_changed.py"))["classify"]
    local.__globals__["ROOT"] = tmp_path
    local_result = local("base", "HEAD", include_worktree=mode == "unstaged_delete")
    assert tuple(local_result[field]) == expected
    assert local_result["changed_paths"] == changed


def test_pr_scope_uses_unique_merge_base_and_excludes_new_main_files(tmp_path: Path) -> None:
    """真实分叉历史不能把 main 的 CI 修改算进四文件模板 PR。"""

    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(tmp_path), *arguments]).decode().strip()

    git("init", "-b", "main")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Fixture")
    (tmp_path / "base.txt").write_text("base")
    git("add", ".")
    git("commit", "-m", "base")
    git("checkout", "-b", "feature")
    paths = ("env.local.example", "env.production.example", "docs/guide.md", "docs/README.md")
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n")
    git("add", ".")
    git("commit", "-m", "four files")
    head = git("rev-parse", "HEAD")
    git("checkout", "main")
    path = tmp_path / ".github/workflows/ci.yml"
    path.parent.mkdir(parents=True)
    path.write_text("name: unrelated\n")
    git("add", ".")
    git("commit", "-m", "main advances")
    changed = SCRIPT["changed_scope"]("main", head, root=tmp_path)
    assert set(changed) == set(paths)
    assert len(changed) == 4
    with pytest.raises(ValueError, match="Git|对象|基线"):
        SCRIPT["changed_scope"]("missing-base", head, root=tmp_path)
    shallow = tmp_path / "shallow-clone"
    git("clone", "--depth", "1", tmp_path.as_uri(), str(shallow))
    with pytest.raises(ValueError, match="shallow.*fetch-depth"):
        SCRIPT["changed_scope"]("HEAD", "HEAD", root=shallow)
    assert SCRIPT["changed_scope"]("HEAD", "HEAD", comparison="direct", root=shallow) == []


def test_env_template_risk_is_content_sensitive_and_does_not_require_product_stacks() -> None:
    """模板注释与身份值变化具有独立配置责任，不能一律归 docs/full。"""
    for expected, before, after in (
        ("comments", "AIMA_LOG_LEVEL=INFO\n", "# note\nAIMA_LOG_LEVEL=INFO\n"),
        ("values", "AIMA_LOG_LEVEL=INFO\n", "AIMA_LOG_LEVEL=DEBUG\n"),
        ("sensitive", "AIMA_FEISHU_CONNECTORS=\n", "AIMA_FEISHU_CONNECTORS=[]\n"),
    ):
        result = CLASSIFY_REQUIREMENTS(
            ["env.local.example"], template_changes={"env.local.example": (before, after)}
        )
        assert result.template_risk == expected
        assert result.template_required
        assert not result.postgres_required
        assert not result.frontend_required
        assert not result.fullstack_required
        assert not result.release_required
        assert result.tooling_windows_required is (expected != "comments")


def test_template_validator_rejects_duplicate_keys_with_lines() -> None:
    validator = runpy.run_path(str(ROOT / "scripts/quality/check_env_templates.py"))
    with pytest.raises(ValueError, match="fixture:2.*重复"):
        validator["parse_template"]("AIMA_LOG_LEVEL=INFO\nAIMA_LOG_LEVEL=DEBUG\n", "fixture")


def test_real_git_scope_covers_staged_unstaged_untracked_deleted_and_renamed(
    tmp_path: Path,
) -> None:
    """本地同源范围必须包含索引与工作区的全部业务变更，忽略运行产物。"""

    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(tmp_path), *arguments]).decode().strip()

    git("init", "-b", "main")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Fixture")
    for name in ("edited.py", "removed.py", "old name.py"):
        (tmp_path / name).write_text("original\n")
    (tmp_path / ".gitignore").write_text(".runtime/\n")
    git("add", ".")
    git("commit", "-m", "base")
    git("branch", "base")
    git("mv", "old name.py", "new name.py")
    (tmp_path / "edited.py").write_text("changed\n")
    (tmp_path / "removed.py").unlink()
    (tmp_path / "untracked.py").write_text("new\n")
    (tmp_path / ".runtime").mkdir()
    (tmp_path / ".runtime/ignored.py").write_text("ignored\n")
    assert set(SCRIPT["changed_scope"]("base", "HEAD", root=tmp_path, include_worktree=True)) == {
        "edited.py",
        "removed.py",
        "old name.py",
        "new name.py",
        "untracked.py",
    }
    assert SCRIPT["changed_scope"]("base", "HEAD", root=tmp_path) == []


def test_real_criss_cross_merge_bases_and_unrelated_histories_fail_closed(tmp_path: Path) -> None:
    """多个合法祖先或无共同祖先都不能静默选一个风险范围。"""

    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(tmp_path), *arguments]).decode().strip()

    git("init", "-b", "main")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Fixture")
    (tmp_path / "file").write_text("base")
    git("add", ".")
    git("commit", "-m", "base")
    tree, original = git("rev-parse", "HEAD^{tree}"), git("rev-parse", "HEAD")
    a = git("commit-tree", tree, "-p", original, "-m", "a")
    b = git("commit-tree", tree, "-p", original, "-m", "b")
    ab = git("commit-tree", tree, "-p", a, "-p", b, "-m", "ab")
    ba = git("commit-tree", tree, "-p", b, "-p", a, "-m", "ba")
    orphan = git("commit-tree", tree, "-m", "orphan")
    assert len(git("merge-base", "--all", ab, ba).splitlines()) == 2
    for base, head in ((ab, ba), (original, orphan), ("0" * 40, original)):
        with pytest.raises(ValueError):
            SCRIPT["changed_scope"](base, head, root=tmp_path)


def test_template_validator_uses_production_identity_validation_without_secret_echo(
    tmp_path: Path,
) -> None:
    """非法 Connector 输入必须由正式启动解析拒绝，错误不得回显其值。"""
    validator = runpy.run_path(str(ROOT / "scripts/quality/check_env_templates.py"))
    for name in (
        "env.local.example",
        "env.production.example",
        "compose.yaml",
        "scripts/dev/local_runtime.py",
    ):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    template = tmp_path / "env.local.example"
    text = template.read_text(encoding="utf-8")
    raw = validator["parse_template"](text, template.name, preserve_syntax=True)[
        "AIMA_FEISHU_CONNECTORS"
    ]
    text = text.replace(
        f"AIMA_FEISHU_CONNECTORS={raw}", "AIMA_FEISHU_CONNECTORS=invalid-private-marker"
    )
    template.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="PlatformSettings") as failure:
        validator["check_templates"](tmp_path)
    assert "invalid-private-marker" not in str(failure.value)


def test_deployment_template_and_unknown_template_risks_preserve_strong_evidence() -> None:
    deployment = CLASSIFY_REQUIREMENTS(
        ["env.production.example"],
        template_changes={"env.production.example": ("AIMA_IMAGE_TAG=a\n", "AIMA_IMAGE_TAG=b\n")},
    )
    assert deployment.runtime_required and deployment.release_required
    assert deployment.tooling_windows_required
    assert not deployment.postgres_required
    unknown = CLASSIFY_REQUIREMENTS(["env.production.example"])
    assert unknown.profile == "full" and unknown.postgres_required and unknown.fullstack_required


def _requirements(*paths: str):  # type: ignore[no-untyped-def]
    """按仓库相对路径返回 CI 证明责任，便于测试不同 changed scope。"""
    return CLASSIFY_REQUIREMENTS(paths)


def test_docs_and_governance_only_do_not_request_product_layers() -> None:
    docs = _requirements("docs/blueprint/06_开发约束与分阶段实施.md")
    governance = _requirements("AGENTS.md", "changes/active/CHG-example/CHANGE.md")

    assert docs.profile == "docs_only"
    assert governance.profile == "governance_only"
    for requirements in (docs, governance):
        assert requirements.repository_required is False
        assert requirements.repository_quality_required is False
        assert requirements.backend_required is False
        assert requirements.frontend_required is False
        assert requirements.contract_required is False
        assert requirements.postgres_required is False
        assert requirements.fullstack_required is False
        assert requirements.stack_smoke_required is False
        assert requirements.report_font_required is False
        assert requirements.postgres_suites == ()
        assert requirements.fullstack_specs == ()


def test_repository_quality_change_does_not_promote_to_product_full() -> None:
    requirements = _requirements(
        "docs/README.md",
        "scripts/quality/check_docs_facts.py",
        "tests/unit/test_docs_facts.py",
    )

    assert requirements.profile == "repository_quality"
    assert requirements.repository_required is True
    assert requirements.repository_quality_required is True
    assert requirements.backend_required is False
    assert requirements.frontend_required is False
    assert requirements.contract_required is False
    assert requirements.postgres_required is False
    assert requirements.fullstack_required is False
    assert requirements.report_font_required is False


def test_frontend_only_keeps_browser_quality_without_postgres_or_real_fullstack() -> None:
    requirements = _requirements(
        "frontend/src/features/voice-plaza/pages/VoicePlazaPage/VoicePlazaPage.vue",
        "frontend/tests/voice-plaza.spec.ts",
    )

    assert requirements.profile == "frontend_only"
    assert requirements.repository_required is True
    assert requirements.frontend_required is True
    assert requirements.backend_required is False
    assert requirements.contract_required is False
    assert requirements.postgres_required is False
    assert requirements.fullstack_required is False
    assert requirements.stack_smoke_required is False


def test_backend_non_persistence_change_can_skip_postgres_and_real_fullstack() -> None:
    requirements = _requirements("backend/src/aima_ugc/platform/time.py")

    assert requirements.profile == "backend_only"
    assert requirements.repository_required is True
    assert requirements.backend_required is True
    assert requirements.frontend_required is False
    assert requirements.contract_required is False
    assert requirements.postgres_required is False
    assert requirements.fullstack_required is False


def test_reporting_change_marks_font_evidence_required() -> None:
    requirements = _requirements("backend/src/aima_ugc/modules/reporting/column_catalog.py")

    assert requirements.profile == "backend_only"
    assert requirements.backend_required is True
    assert requirements.report_font_required is True


def test_report_postgres_workflow_is_a_selected_ci_target() -> None:
    requirements = _requirements("tests/integration/reporting/test_database_reports.py")

    assert requirements.postgres_required is True
    assert requirements.postgres_targets == (
        "tests/integration/reporting/test_database_reports.py",
    )


def test_full_postgres_evidence_includes_report_workflows() -> None:
    assert "reporting" in SCRIPT["ALL_POSTGRES_SUITES"]
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "if selected reporting; then" in workflow
    assert "AIMA_REPORT_TEST_DATABASE=1 uv run pytest tests/integration/reporting -q" in workflow
    postgres_step = workflow.split('if [[ -n "${POSTGRES_TARGETS}" ]]; then', 1)[1]
    assert (
        'AIMA_REPORT_TEST_DATABASE=1 uv run pytest "${targets[@]}" -q'
        in (postgres_step.split("fi", 1)[0])
    )


def test_postgres_report_rendering_has_its_own_cjk_font_dependency() -> None:
    """PG 在独立 runner 渲染真实文件，不能借用 core Job 安装的字体。"""
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    postgres_job = workflow.split("  postgres-integration:", 1)[1].split("\n  real-fullstack:", 1)[
        0
    ]
    font_step = postgres_job.split("- name: Install report integration CJK font", 1)[1]
    font_step = font_step.split("- name:", 1)[0]
    assert "fonts-noto-cjk" in font_step
    assert "report_font_required == 'true'" in font_step
    assert "' all '" in font_step
    assert "' reporting '" in font_step
    assert postgres_job.index("Install report integration CJK font") < postgres_job.index(
        "Selected PostgreSQL integration evidence"
    )
    targeted = _requirements("tests/integration/reporting/test_database_reports.py")
    full = _requirements(".github/workflows/ci.yml")
    assert targeted.report_font_required is True
    assert full.report_font_required is True


def test_http_producer_change_requires_contract_drift_and_real_cross_component_proof() -> None:
    requirements = _requirements("backend/src/aima_ugc/entrypoints/api_main.py")

    assert requirements.profile == "contract"
    assert requirements.backend_required is True
    assert requirements.frontend_required is True
    assert requirements.contract_required is True
    assert requirements.postgres_required is False
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == FULLSTACK_ALL


def test_collection_persistence_change_runs_only_collection_postgres_and_relevant_golden_path() -> (
    None
):
    requirements = _requirements("backend/src/aima_ugc/modules/collection/tables.py")

    assert requirements.profile == "persistence"
    assert requirements.backend_required is True
    assert requirements.postgres_required is True
    assert requirements.postgres_suites == ("collection",)
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == (
        "collection-plan-search-config.spec.ts",
        "comment-supplement.spec.ts",
    )


def test_content_integration_test_change_runs_only_changed_postgres_target_without_fullstack() -> (
    None
):
    requirements = _requirements("tests/integration/content/test_postgres_ingestion.py")

    assert requirements.profile == "persistence"
    assert requirements.backend_required is True
    assert requirements.postgres_required is True
    assert requirements.postgres_targets == (
        "tests/integration/content/test_postgres_ingestion.py",
    )
    assert requirements.postgres_suites == ()
    assert requirements.fullstack_required is False
    assert requirements.fullstack_specs == ()


def test_vehicle_integration_test_change_runs_only_changed_postgres_target() -> None:
    requirements = _requirements(
        "tests/integration/vehicles/test_content_reclassification_postgres.py"
    )

    assert requirements.profile == "persistence"
    assert requirements.postgres_required is True
    assert requirements.postgres_targets == (
        "tests/integration/vehicles/test_content_reclassification_postgres.py",
    )
    assert requirements.postgres_suites == ()
    assert requirements.fullstack_required is False


def test_vehicle_persistence_change_runs_vehicle_postgres_suite() -> None:
    requirements = _requirements(
        "backend/src/aima_ugc/adapters/persistence/postgres/content_reclassification.py"
    )

    assert requirements.postgres_required is True
    assert requirements.postgres_suites == ("vehicles",)


def test_ingestion_persistence_runs_content_and_ingestion_postgres_suites() -> None:
    requirements = _requirements("backend/src/aima_ugc/modules/ingestion/imports.py")

    assert requirements.profile == "persistence"
    assert requirements.postgres_required is True
    assert requirements.postgres_suites == ("content", "ingestion")
    assert requirements.fullstack_specs == (
        "excel-import.spec.ts",
        "stage12-historical-analysis.spec.ts",
    )


def test_unknown_persistence_adapter_fails_closed_to_all_postgres_suites() -> None:
    requirements = _requirements("backend/src/aima_ugc/adapters/persistence/postgres/analysis.py")

    assert requirements.postgres_required is True
    assert requirements.postgres_suites == POSTGRES_ALL
    assert requirements.fullstack_specs == (
        "analysis-streaming.spec.ts",
        "stage12-historical-analysis.spec.ts",
    )


def test_integration_shared_conftest_fails_closed_to_all_postgres_suites() -> None:
    requirements = _requirements("tests/integration/conftest.py")

    assert requirements.postgres_required is True
    assert requirements.postgres_suites == POSTGRES_ALL


def test_contract_change_runs_producer_consumer_and_all_real_golden_paths() -> None:
    requirements = _requirements("contracts/openapi.json")

    assert requirements.profile == "contract"
    assert requirements.backend_required is True
    assert requirements.frontend_required is True
    assert requirements.contract_required is True
    assert requirements.postgres_required is False
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == FULLSTACK_ALL


def test_contract_test_change_stays_backend_only_instead_of_promoting_cross_component() -> None:
    requirements = _requirements("tests/contracts/test_canonical_v1.py")

    assert requirements.profile == "backend_only"
    assert requirements.backend_required is True
    assert requirements.frontend_required is False
    assert requirements.contract_required is False
    assert requirements.postgres_required is False
    assert requirements.fullstack_required is False


def test_fullstack_spec_change_runs_only_that_real_golden_path() -> None:
    requirements = _requirements("frontend/e2e-fullstack/manual-relevance-review.spec.ts")

    assert requirements.frontend_required is True
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == ("manual-relevance-review.spec.ts",)


def test_analysis_streaming_spec_is_selected_independently() -> None:
    requirements = _requirements("frontend/e2e-fullstack/analysis-streaming.spec.ts")

    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == ("analysis-streaming.spec.ts",)


def test_comment_supplement_spec_is_selected_independently() -> None:
    requirements = _requirements("frontend/e2e-fullstack/comment-supplement.spec.ts")

    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == ("comment-supplement.spec.ts",)


def test_administration_persistence_runs_admin_product_golden_path_and_all_postgres() -> None:
    requirements = _requirements(
        "backend/src/aima_ugc/adapters/persistence/postgres/notifications.py"
    )

    assert requirements.backend_required is True
    assert requirements.postgres_required is True
    assert requirements.postgres_suites == POSTGRES_ALL
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == ("admin-product-capabilities.spec.ts",)


def test_analysis_scheme_persistence_runs_admin_and_frozen_run_golden_paths() -> None:
    requirements = _requirements(
        "backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py"
    )

    assert requirements.backend_required is True
    assert requirements.postgres_required is True
    assert requirements.postgres_suites == POSTGRES_ALL
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == (
        "admin-product-capabilities.spec.ts",
        "stage12-historical-analysis.spec.ts",
    )


def test_fullstack_control_plane_change_runs_entire_real_suite() -> None:
    requirements = _requirements("frontend/playwright.fullstack.config.ts")

    assert requirements.profile == "full"
    assert requirements.postgres_required is True
    assert requirements.postgres_suites == POSTGRES_ALL
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == FULLSTACK_ALL


def test_unknown_new_fullstack_spec_fails_closed_to_entire_suite() -> None:
    requirements = _requirements("frontend/e2e-fullstack/new-critical-flow.spec.ts")

    assert requirements.frontend_required is True
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == FULLSTACK_ALL


def test_mixed_frontend_and_backend_change_selects_known_journey_instead_of_all() -> None:
    requirements = _requirements(
        "frontend/src/features/voice-plaza/store.ts",
        "backend/src/aima_ugc/platform/time.py",
    )

    assert requirements.profile == "cross_component"
    assert requirements.frontend_required is True
    assert requirements.backend_required is True
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == ("manual-relevance-review.spec.ts",)


def test_workbench_persistence_change_uses_exact_postgres_targets() -> None:
    requirements = _requirements("backend/src/aima_ugc/adapters/persistence/postgres/workbench.py")

    assert requirements.postgres_required is True
    assert requirements.postgres_targets == (
        "tests/integration/content/test_workbench_runtime.py",
        "tests/integration/content/test_workbench_scheme_bootstrap.py",
    )
    assert requirements.postgres_suites == ()
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == ("analysis-streaming.spec.ts",)


def test_historical_import_persistence_uses_owned_domain_suites_and_known_journeys() -> None:
    requirements = _requirements(
        "backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py"
    )

    assert requirements.postgres_required is True
    assert requirements.postgres_targets == ()
    assert requirements.postgres_suites == ("content", "ingestion")
    assert requirements.fullstack_specs == (
        "excel-import.spec.ts",
        "stage12-historical-analysis.spec.ts",
    )


def test_unknown_new_user_journey_fails_closed_to_fullstack() -> None:
    requirements = _requirements(
        "frontend/src/features/new-critical-flow/page.vue",
        "backend/src/aima_ugc/bootstrap/new_critical_flow_http.py",
    )

    assert requirements.profile == "contract"
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == FULLSTACK_ALL


def test_workbench_frontend_and_backend_change_runs_its_real_analysis_journey() -> None:
    requirements = _requirements(
        "backend/src/aima_ugc/adapters/persistence/postgres/workbench.py",
        "frontend/src/features/workbench/pages/WorkbenchPage.vue",
    )

    assert requirements.profile == "cross_component"
    assert requirements.frontend_required is True
    assert requirements.backend_required is True
    assert requirements.postgres_required is True
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == ("analysis-streaming.spec.ts",)


def test_frontend_dependency_audit_only_runs_for_dependency_inputs() -> None:
    ordinary = _requirements("frontend/src/features/workbench/pages/WorkbenchPage.vue")
    lock_change = _requirements("frontend/package-lock.json")

    assert ordinary.frontend_required is True
    assert ordinary.frontend_audit_required is False
    assert lock_change.frontend_required is True
    assert lock_change.frontend_audit_required is True


def test_wheel_build_only_runs_for_python_package_inputs() -> None:
    ordinary = _requirements("backend/src/aima_ugc/platform/time.py")
    package = _requirements("pyproject.toml")

    assert ordinary.backend_required is True
    assert ordinary.package_required is False
    assert package.package_required is True


def test_ci_self_change_and_unknown_path_fail_closed_to_full() -> None:
    for path in (
        ".github/workflows/ci.yml",
        "scripts/quality/classify_ci_scope.py",
        "tests/unit/test_actions_runner_optimization.py",
        "tests/unit/test_ci_workflow_structure.py",
        "tools/unclassified.machine",
    ):
        requirements = _requirements(path)

        assert requirements.profile == "full"
        assert requirements.repository_required is True
        assert requirements.repository_quality_required is True
        assert requirements.backend_required is True
        assert requirements.frontend_required is True
        assert requirements.contract_required is True
        assert requirements.postgres_required is True
        assert requirements.postgres_suites == POSTGRES_ALL
        assert requirements.fullstack_required is True
        assert requirements.stack_smoke_required is True
        assert requirements.report_font_required is True
        assert requirements.fullstack_specs == FULLSTACK_ALL


def test_mixed_docs_and_frontend_use_the_product_scope_instead_of_falling_back_full() -> None:
    requirements = _requirements(
        "docs/blueprint/06_开发约束与分阶段实施.md",
        "frontend/src/App.vue",
    )

    assert requirements.profile == "frontend_only"
    assert requirements.frontend_required is True
    assert requirements.backend_required is False
    assert requirements.postgres_required is False
    assert requirements.fullstack_required is False


def test_repository_quality_can_mix_with_backend_without_promoting_to_full() -> None:
    requirements = _requirements(
        "scripts/quality/check_docs_facts.py",
        "backend/src/aima_ugc/platform/time.py",
    )

    assert requirements.profile == "backend_only"
    assert requirements.repository_quality_required is True
    assert requirements.backend_required is True
    assert requirements.frontend_required is False
    assert requirements.postgres_required is False


def test_github_output_exposes_each_required_layer_and_selected_suites(tmp_path: Path) -> None:
    output = tmp_path / "github-output"
    requirements = _requirements("backend/src/aima_ugc/modules/ingestion/imports.py")

    WRITE_GITHUB_OUTPUT(output, requirements, changed_count=1)

    values = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if line
    )
    assert values["profile"] == "persistence"
    assert values["repository_required"] == "true"
    assert values["repository_quality_required"] == "false"
    assert values["backend_required"] == "true"
    assert values["frontend_required"] == "false"
    assert values["contract_required"] == "false"
    assert values["postgres_required"] == "true"
    assert values["postgres_targets"] == ""
    assert values["postgres_suites"] == "content ingestion"
    assert values["frontend_audit_required"] == "false"
    assert values["package_required"] == "false"
    assert values["fullstack_required"] == "true"
    assert values["stack_smoke_required"] == "false"
    assert values["report_font_required"] == "false"
    assert values["fullstack_specs"] == "excel-import.spec.ts stage12-historical-analysis.spec.ts"
    assert values["changed_count"] == "1"


def test_known_backend_and_frontend_paths_select_targeted_development_evidence() -> None:
    """高频功能路径优先选择直接测试目标，共享/未知边界继续 fail closed。"""
    analysis = _requirements("backend/src/aima_ugc/modules/analysis/content_analysis_job.py")
    voice = _requirements("frontend/src/features/voice-plaza/store.ts")
    workbench = _requirements("frontend/src/features/workbench/components/WorkbenchFilters.vue")
    unknown_backend = _requirements("backend/src/aima_ugc/bootstrap/unclassified_worker.py")
    ci_self = _requirements(".github/workflows/ci.yml")

    assert analysis.backend_targets == (
        "tests/api/test_analysis_all_scope.py",
        "tests/api/test_analysis_runtime_capability.py",
        "tests/api/test_analysis_taxonomy.py",
        "tests/unit/analysis",
        "tests/unit/content/test_stage12_analysis_planner.py",
    )
    assert voice.frontend_unit_targets == (
        "frontend/tests/analysis-all-scope.spec.ts",
        "frontend/tests/voice-plaza-design.spec.ts",
        "frontend/tests/voice-plaza-media-preview.spec.ts",
        "frontend/tests/voice-plaza.spec.ts",
    )
    assert voice.frontend_e2e_specs == (
        "frontend/e2e/voice-plaza-design.spec.ts",
        "frontend/e2e/voice-plaza-media-carousel.spec.ts",
        "frontend/e2e/voice-plaza-review-regressions.spec.ts",
        "frontend/e2e/voice-plaza.spec.ts",
    )
    assert workbench.frontend_unit_targets == ("frontend/tests/workbench.spec.ts",)
    assert workbench.frontend_e2e_specs == ("frontend/e2e/workbench.spec.ts",)
    assert unknown_backend.backend_targets == ("all",)
    shared_platform = _requirements("backend/src/aima_ugc/platform/time.py")
    shared_ui = _requirements("frontend/src/shared/ui/AimaMultiSelect.vue")
    assert shared_platform.backend_targets == ("all",)
    assert shared_ui.frontend_unit_targets == ("all",)
    assert shared_ui.frontend_e2e_specs == ("all",)
    assert ci_self.backend_targets == ("all",)
    assert ci_self.frontend_unit_targets == ("all",)
    assert ci_self.frontend_e2e_specs == ("all",)


def test_github_output_exposes_backend_and_frontend_selected_targets(tmp_path: Path) -> None:
    """CI Plan 必须把同一 classifier 的 Backend/Frontend 选择传给后续并行 Job。"""
    output = tmp_path / "github-output"
    requirements = _requirements("frontend/src/features/workbench/components/WorkbenchFilters.vue")

    WRITE_GITHUB_OUTPUT(output, requirements, changed_count=1)

    values = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if line
    )
    assert values["backend_targets"] == ""
    assert values["frontend_unit_targets"] == "frontend/tests/workbench.spec.ts"
    assert values["frontend_e2e_specs"] == "frontend/e2e/workbench.spec.ts"


def test_known_backend_domains_include_direct_api_evidence_without_global_api_suite() -> None:
    """高频 Backend Owner 的 API Evidence 与 Unit 一起由 classifier 精确选择。"""
    collection = _requirements("backend/src/aima_ugc/modules/collection/service.py")
    ingestion = _requirements("backend/src/aima_ugc/modules/ingestion/imports.py")
    vehicles = _requirements("backend/src/aima_ugc/modules/vehicles/service.py")

    assert "tests/api/test_stage8e_collection_runs.py" in collection.backend_targets
    assert "tests/api/test_stage8f_collection_strategy.py" in collection.backend_targets
    assert "tests/api/test_stage12_historical_imports.py" in ingestion.backend_targets
    assert "tests/api/test_stage8b_imports.py" in ingestion.backend_targets
    assert "tests/api/test_stage8c_import_batches.py" in ingestion.backend_targets
    assert vehicles.backend_targets == (
        "tests/api/test_brand_vehicle_stage2_contract.py",
        "tests/unit/vehicles",
    )


def test_selected_backend_and_frontend_targets_exist() -> None:
    """精准 selector 只能引用仓库中真实存在的测试资产。"""
    representative = (
        _requirements("backend/src/aima_ugc/modules/analysis/content_analysis_job.py"),
        _requirements("backend/src/aima_ugc/modules/collection/service.py"),
        _requirements("backend/src/aima_ugc/modules/content/service.py"),
        _requirements("backend/src/aima_ugc/modules/ingestion/imports.py"),
        _requirements("backend/src/aima_ugc/modules/vehicles/service.py"),
        _requirements("frontend/src/features/voice-plaza/store.ts"),
        _requirements("frontend/src/features/workbench/components/WorkbenchFilters.vue"),
        _requirements("frontend/src/features/admin-configuration/store.ts"),
        _requirements("frontend/src/features/task-center/store.ts"),
        _requirements("frontend/src/features/collection-strategy/store.ts"),
        _requirements("frontend/src/features/collection-runtime/store.ts"),
    )
    for requirements in representative:
        for target in (
            *requirements.backend_targets,
            *requirements.frontend_unit_targets,
            *requirements.frontend_e2e_specs,
        ):
            if target != "all":
                assert (ROOT / target).exists(), target
