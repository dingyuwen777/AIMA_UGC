from __future__ import annotations

import runpy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = runpy.run_path(str(ROOT / "scripts" / "quality" / "classify_ci_scope.py"))
CLASSIFY_REQUIREMENTS = CLASSIFIER["classify_requirements"]


def _workflow_triggers(workflow: dict[object, object]) -> dict[str, object]:
    """兼容 PyYAML 1.1 把顶层 `on` 解析成布尔值 True 的行为。"""
    triggers = workflow.get("on") or workflow.get(True)
    assert isinstance(triggers, dict)
    return triggers


def test_repository_quality_isolated_from_product_stacks() -> None:
    requirements = CLASSIFY_REQUIREMENTS(
        (
            "docs/README.md",
            "scripts/quality/check_docs_facts.py",
            "tests/unit/test_docs_facts.py",
        )
    )

    assert requirements.profile == "repository_quality"
    assert requirements.repository_quality_required is True
    assert requirements.backend_required is False
    assert requirements.frontend_required is False
    assert requirements.postgres_required is False
    assert requirements.fullstack_required is False


def test_repository_quality_test_family_stays_out_of_product_backend() -> None:
    for path in (
        "tests/unit/test_docs_navigation.py",
        "tests/unit/test_issue_acceptance_profile.py",
    ):
        requirements = CLASSIFY_REQUIREMENTS((path,))
        assert requirements.profile == "repository_quality"
        assert requirements.repository_quality_required is True
        assert requirements.backend_required is False


def test_repository_quality_scripts_use_an_explicit_allowlist() -> None:
    lightweight = CLASSIFY_REQUIREMENTS(("scripts/quality/scan_secrets.py",))
    assert lightweight.profile == "repository_quality"
    assert lightweight.repository_quality_required is True
    assert lightweight.backend_required is False

    for path in (
        "scripts/quality/check_architecture.py",
        "scripts/quality/check_table_ownership.py",
    ):
        requirements = CLASSIFY_REQUIREMENTS((path,))
        assert requirements.profile == "full"
        assert requirements.backend_required is True
        assert requirements.postgres_suites == ("all",)
        assert requirements.fullstack_specs == ("all",)


def test_ci_impact_regression_is_itself_fail_closed_to_full() -> None:
    requirements = CLASSIFY_REQUIREMENTS(("tests/unit/test_ci_test_impact_optimization.py",))

    assert requirements.profile == "full"
    assert requirements.postgres_suites == ("all",)
    assert requirements.fullstack_specs == ("all",)


def test_persistence_leaf_selects_only_owned_postgres_suite() -> None:
    requirements = CLASSIFY_REQUIREMENTS(("backend/src/aima_ugc/modules/collection/tables.py",))

    assert requirements.postgres_required is True
    assert requirements.postgres_suites == ("collection",)
    assert requirements.fullstack_specs == ("collection-plan-search-config.spec.ts",)


def test_migration_compatibility_verifier_selects_migration_suite() -> None:
    requirements = CLASSIFY_REQUIREMENTS(
        ("tests/integration/database/verify_migration_compatibility.py",)
    )

    assert requirements.profile == "persistence"
    assert requirements.postgres_required is True
    assert requirements.postgres_suites == ("migration",)
    assert requirements.fullstack_required is False


def test_unknown_persistence_and_ci_self_fail_closed() -> None:
    persistence = CLASSIFY_REQUIREMENTS(
        ("backend/src/aima_ugc/adapters/persistence/postgres/analysis.py",)
    )
    ci_self = CLASSIFY_REQUIREMENTS((".github/workflows/ci.yml",))

    assert persistence.postgres_suites == ("all",)
    assert ci_self.profile == "full"
    assert ci_self.postgres_suites == ("all",)
    assert ci_self.fullstack_specs == ("all",)


def test_ci_workflow_uses_selected_postgres_suites_and_no_postgres_font_install() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)

    assert "postgres_suites" in text
    assert "POSTGRES_SUITES" in text
    assert "Selected PostgreSQL integration evidence" in text
    assert "repository_quality_required" in text
    assert "Repository quality static and targeted regression" in text

    postgres_job = workflow["jobs"]["postgres-integration"]
    postgres_text = yaml.safe_dump(postgres_job, allow_unicode=True)
    assert "fonts-noto-cjk" not in postgres_text

    quality_steps = workflow["jobs"]["quality-core"]["steps"]
    font_step = next(step for step in quality_steps if step.get("name") == "Install report validation CJK font")
    assert font_step["if"] == "steps.classify.outputs.report_font_required == 'true'"


def test_draft_prs_are_skipped_at_job_level_instead_of_failed_inside_ci() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)

    quality_core = workflow["jobs"]["quality-core"]
    ci_gate = workflow["jobs"]["ci-gate"]
    assert "draft == false" in str(quality_core["if"])
    assert "draft == false" in str(ci_gate["if"])
    assert "Defer full CI while PR is Draft" not in text


def test_runtime_draft_pr_is_skipped_before_allocating_compose_work() -> None:
    text = (ROOT / ".github" / "workflows" / "runtime.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)

    compose = workflow["jobs"]["compose-golden-path"]
    assert "draft == false" in str(compose["if"])
    assert "Defer Runtime Acceptance while PR is Draft" not in text


def test_release_dry_run_only_tracks_release_machine_inputs() -> None:
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    triggers = _workflow_triggers(workflow)
    pull_request = triggers["pull_request"]
    assert isinstance(pull_request, dict)
    paths = pull_request["paths"]

    assert paths == [
        ".github/workflows/release.yml",
        "Dockerfile",
        "compose.yaml",
        "env.production.example",
        "tests/unit/test_docker_build_sources.py",
        "tests/unit/test_release_workflow.py",
    ]
    assert workflow["concurrency"]["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"


def test_change_archivist_skip_is_after_exact_archive_allowlist() -> None:
    text = (ROOT / ".github" / "workflows" / "change-archive.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    archive_job = workflow["jobs"]["archive"]
    names = [step.get("name") for step in archive_job["steps"]]

    verify_index = names.index("Verify archive gate and exact diff allowlist")
    commit_index = names.index("Commit and push archive to main")
    assert verify_index < commit_index
    assert "[skip ci]" in text
    assert "git diff --cached --name-only --no-renames" in text
    assert "changes/(active|archive)" in text
