from __future__ import annotations

import runpy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = runpy.run_path(str(ROOT / "scripts" / "quality" / "classify_ci_scope.py"))
CLASSIFY_REQUIREMENTS = CLASSIFIER["classify_requirements"]


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


def test_persistence_leaf_selects_only_owned_postgres_suite() -> None:
    requirements = CLASSIFY_REQUIREMENTS(("backend/src/aima_ugc/modules/collection/tables.py",))

    assert requirements.postgres_required is True
    assert requirements.postgres_suites == ("collection",)
    assert requirements.fullstack_specs == ("collection-plan-search-config.spec.ts",)


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


def test_draft_prs_are_skipped_at_job_level_instead_of_failed_inside_ci() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)

    quality_core = workflow["jobs"]["quality-core"]
    ci_gate = workflow["jobs"]["ci-gate"]
    assert "draft == false" in str(quality_core["if"])
    assert "draft == false" in str(ci_gate["if"])
    assert "Defer full CI while PR is Draft" not in text


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
