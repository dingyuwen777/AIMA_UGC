from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = runpy.run_path(str(ROOT / "scripts" / "quality" / "classify_ci_scope.py"))
CLASSIFY_REQUIREMENTS = SCRIPT["classify_requirements"]
WRITE_GITHUB_OUTPUT = SCRIPT["_write_github_output"]
FULLSTACK_ALL = SCRIPT["FULLSTACK_ALL"]


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
        assert requirements.backend_required is False
        assert requirements.frontend_required is False
        assert requirements.contract_required is False
        assert requirements.postgres_required is False
        assert requirements.fullstack_required is False
        assert requirements.stack_smoke_required is False
        assert requirements.fullstack_specs == ()


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


def test_http_producer_change_requires_contract_drift_and_real_cross_component_proof() -> None:
    requirements = _requirements("backend/src/aima_ugc/entrypoints/api_main.py")

    assert requirements.profile == "contract"
    assert requirements.backend_required is True
    assert requirements.frontend_required is True
    assert requirements.contract_required is True
    assert requirements.postgres_required is False
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == FULLSTACK_ALL


def test_collection_persistence_change_runs_postgres_and_relevant_golden_path() -> None:
    requirements = _requirements("backend/src/aima_ugc/modules/collection/tables.py")

    assert requirements.profile == "persistence"
    assert requirements.backend_required is True
    assert requirements.postgres_required is True
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == ("collection-plan-search-config.spec.ts",)


def test_integration_test_change_runs_postgres_without_promoting_itself_to_real_fullstack() -> None:
    requirements = _requirements("tests/integration/content/test_postgres_ingestion.py")

    assert requirements.profile == "persistence"
    assert requirements.backend_required is True
    assert requirements.postgres_required is True
    assert requirements.fullstack_required is False
    assert requirements.fullstack_specs == ()


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


def test_fullstack_control_plane_change_runs_entire_real_suite() -> None:
    requirements = _requirements("frontend/playwright.fullstack.config.ts")

    assert requirements.profile == "full"
    assert requirements.postgres_required is True
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == FULLSTACK_ALL


def test_unknown_new_fullstack_spec_fails_closed_to_entire_suite() -> None:
    requirements = _requirements("frontend/e2e-fullstack/new-critical-flow.spec.ts")

    assert requirements.frontend_required is True
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == FULLSTACK_ALL


def test_mixed_frontend_and_backend_change_requires_cross_component_proof() -> None:
    requirements = _requirements(
        "frontend/src/features/voice-plaza/store.ts",
        "backend/src/aima_ugc/platform/time.py",
    )

    assert requirements.profile == "cross_component"
    assert requirements.frontend_required is True
    assert requirements.backend_required is True
    assert requirements.fullstack_required is True
    assert requirements.fullstack_specs == FULLSTACK_ALL


def test_ci_self_change_and_unknown_path_fail_closed_to_full() -> None:
    for path in (".github/workflows/ci.yml", "tools/unclassified.machine"):
        requirements = _requirements(path)

        assert requirements.profile == "full"
        assert requirements.repository_required is True
        assert requirements.backend_required is True
        assert requirements.frontend_required is True
        assert requirements.contract_required is True
        assert requirements.postgres_required is True
        assert requirements.fullstack_required is True
        assert requirements.stack_smoke_required is True
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


def test_github_output_exposes_each_required_layer_and_selected_specs(tmp_path: Path) -> None:
    output = tmp_path / "github-output"
    requirements = _requirements("backend/src/aima_ugc/modules/ingestion/imports.py")

    WRITE_GITHUB_OUTPUT(output, requirements, changed_count=1)

    values = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if line
    )
    assert values["profile"] == "persistence"
    assert values["repository_required"] == "true"
    assert values["backend_required"] == "true"
    assert values["frontend_required"] == "false"
    assert values["contract_required"] == "false"
    assert values["postgres_required"] == "true"
    assert values["fullstack_required"] == "true"
    assert values["stack_smoke_required"] == "false"
    assert values["fullstack_specs"] == "excel-import.spec.ts stage12-historical-analysis.spec.ts"
    assert values["changed_count"] == "1"
