from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = runpy.run_path(str(ROOT / "scripts" / "quality" / "classify_ci_scope.py"))
CLASSIFY_REQUIREMENTS = SCRIPT["classify_requirements"]
WRITE_GITHUB_OUTPUT = SCRIPT["_write_github_output"]
FULLSTACK_ALL = SCRIPT["FULLSTACK_ALL"]
POSTGRES_ALL = SCRIPT["POSTGRES_ALL"]


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
    assert requirements.fullstack_required is False


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


def test_workbench_frontend_and_backend_change_has_no_unrelated_real_fullstack() -> None:
    requirements = _requirements(
        "backend/src/aima_ugc/adapters/persistence/postgres/workbench.py",
        "frontend/src/features/workbench/pages/WorkbenchPage.vue",
    )

    assert requirements.profile == "cross_component"
    assert requirements.frontend_required is True
    assert requirements.backend_required is True
    assert requirements.postgres_required is True
    assert requirements.fullstack_required is False


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
