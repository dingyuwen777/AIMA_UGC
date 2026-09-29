from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = runpy.run_path(str(ROOT / "scripts" / "quality" / "classify_ci_scope.py"))
CLASSIFY_REQUIREMENTS = CLASSIFIER["classify_requirements"]


def _section(text: str, start: str, end: str) -> str:
    """从受版本控制的 Workflow 文本中提取唯一结构段，避免引入 YAML 解析依赖。"""
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


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
    assert requirements.fullstack_specs == (
        "collection-plan-search-config.spec.ts",
        "comment-supplement.spec.ts",
    )


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
    """完整后端单测所需字体留在 Core，PostgreSQL Job 不重复安装。"""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "postgres_suites" in text
    assert "POSTGRES_SUITES" in text
    assert "Selected PostgreSQL integration evidence" in text
    assert "repository_quality_required" in text
    assert "Repository quality static and targeted regression" in text

    postgres_job = _section(text, "  postgres-integration:\n", "  real-fullstack:\n")
    assert "fonts-noto-cjk" not in postgres_job
    assert (
        "      POSTGRES_SUITES: ${{ needs.ci-plan.outputs.postgres_suites }}\n" in postgres_job
    )
    assert "uv run pytest tests/integration/vehicles -q" in postgres_job

    font = _section(
        text,
        "      - name: Install report validation CJK font\n",
        "      - name: Verify required runtime versions\n",
    )
    assert "needs.ci-plan.outputs.backend_targets == 'all'" in font
    assert "needs.ci-plan.outputs.report_font_required == 'true'" in font


def test_frontend_and_backend_selected_targets_are_consumed_by_core() -> None:
    """Core 使用 plan 选出的直接目标；all 仍是 fail-closed 全量路径。"""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "BACKEND_TARGETS: ${{ needs.ci-plan.outputs.backend_targets }}" in text
    assert "FRONTEND_UNIT_TARGETS: ${{ needs.ci-plan.outputs.frontend_unit_targets }}" in text
    assert "FRONTEND_BROWSER_TARGETS: ${{ needs.ci-plan.outputs.frontend_browser_targets }}" in text
    assert '[[ " ${BACKEND_TARGETS} " == *" all "* ]]' in text
    assert '[[ " ${FRONTEND_UNIT_TARGETS} " == *" all "* ]]' in text
    assert '[[ " ${FRONTEND_BROWSER_TARGETS} " == *" all "* ]]' in text


def test_draft_pr_required_contexts_fail_closed_without_running_full_ci() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    core = _section(text, "  quality-core:\n", "  postgres-integration:\n")

    assert "      - name: Block Draft required evidence\n" in core
    assert "github.event.pull_request.draft == true" in core
    assert core.index("Block Draft required evidence") < core.index("      - name: Checkout")
    assert "  ci-gate:\n    name: CI Gate\n    if: always()\n" in text
    assert "github.event.pull_request.draft == false" not in text


def test_runtime_draft_pr_fails_closed_before_compose_setup() -> None:
    text = (ROOT / ".github" / "workflows" / "runtime.yml").read_text(encoding="utf-8")
    job = text.split("  compose-golden-path:\n", 1)[1]

    assert "      - name: Block Draft required evidence\n" in job
    assert "github.event.pull_request.draft == true" in job
    assert job.index("Block Draft required evidence") < job.index("      - name: Checkout")
    assert "github.event.pull_request.draft == false" not in job


def test_release_dry_run_only_tracks_release_machine_inputs() -> None:
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    trigger_block = _section(text, "on:\n", "permissions:\n")

    assert (
        "  pull_request:\n"
        "    branches:\n"
        "      - main\n"
        "    types:\n"
        "      - opened\n"
        "      - reopened\n"
        "      - ready_for_review\n"
        "    paths:\n"
        "      - .github/workflows/release.yml\n"
        "      - Dockerfile\n"
        "      - compose.yaml\n"
        "      - compose.windows.yaml\n"
        "      - env.production.example\n"
        "      - scripts/release/release_bundle.py\n"
        "      - scripts/deploy/start_compose.py\n"
        "      - scripts/deploy/stop_compose.py\n"
        "      - scripts/deploy/reset_keep_vehicle_catalog.sh\n"
        "      - scripts/release/build_local_release.ps1\n"
        "      - tests/unit/test_docker_build_sources.py\n"
        "      - tests/unit/test_release_workflow.py\n"
        "      - tests/unit/test_release_bundle.py\n"
        "      - tests/unit/test_compose_auto_scripts.py\n" in trigger_block
    )
    for retired_path in (
        "docs/02_环境运行与部署.md",
        "docs/roadmap/02_生产上线实施路线.md",
        "docs/appendix/11_生产部署与离线Release方案.md",
    ):
        assert retired_path not in trigger_block
    assert "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n" in text


def test_change_archivist_skip_is_after_exact_archive_allowlist() -> None:
    text = (ROOT / ".github" / "workflows" / "change-archive.yml").read_text(encoding="utf-8")

    verify_index = text.index("      - name: Verify archive gate and exact diff allowlist")
    commit_index = text.index("      - name: Commit and push archive to main")
    assert verify_index < commit_index
    assert "[skip ci]" in text
    assert "git diff --cached --name-only --no-renames" in text
    assert "changes/(active|archive)" in text
