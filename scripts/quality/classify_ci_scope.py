"""按变更路径保守计算 AIMA CI 需要保留的独立证明责任。"""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from pathlib import Path

ALL_FULLSTACK_SPECS = (
    "admin-product-capabilities.spec.ts",
    "analysis-streaming.spec.ts",
    "collection-plan-search-config.spec.ts",
    "comment-supplement.spec.ts",
    "excel-import.spec.ts",
    "manual-relevance-review.spec.ts",
    "role-export-preferences.spec.ts",
    "stage12-historical-analysis.spec.ts",
)
FULLSTACK_ALL = ("all",)
ALL_POSTGRES_SUITES = (
    "migration",
    "platform",
    "readiness",
    "database",
    "jobs",
    "collection",
    "content",
    "ingestion",
    "vehicles",
    "reporting",
)
POSTGRES_ALL = ("all",)
BACKEND_ALL = ("all",)
FRONTEND_ALL = ("all",)


DOCS_ONLY_EXACT = {"README.md", "USAGE.md"}
GOVERNANCE_ONLY_EXACT = {"AGENTS.md"}
DOCS_ONLY_PREFIXES = ("docs/",)
DOCS_ONLY_SUFFIXES = {".md", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
GOVERNANCE_ONLY_PREFIXES = ("changes/", ".agents/")

CI_SELF_EXACT = {
    ".github/workflows/ci.yml",
    ".github/workflows/fullstack.yml",
    "scripts/quality/classify_ci_scope.py",
    "scripts/quality/resolve_main_evidence.py",
    "tests/unit/test_ci_scope.py",
    "tests/unit/test_ci_test_impact_optimization.py",
    "tests/unit/test_ci_workflow_structure.py",
    "tests/unit/test_ci_main_evidence_reuse.py",
    "tests/unit/test_actions_runner_optimization.py",
    "tests/unit/test_validate_changed.py",
    "scripts/quality/check_env_templates.py",
    "scripts/quality/verify_pr_baseline.py",
}
ENV_TEMPLATES = frozenset({"env.local.example", "env.production.example"})
RUNTIME_EXACT = frozenset(
    {
        ".dockerignore",
        "Dockerfile",
        "alembic.ini",
        "compose.yaml",
        "compose.windows.yaml",
        "frontend/nginx.conf",
        "pyproject.toml",
        "uv.lock",
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/vite.config.ts",
    }
)
RUNTIME_PREFIXES = (
    "scripts/deploy/",
    "migrations/",
    "backend/src/aima_ugc/entrypoints/",
    "backend/src/aima_ugc/bootstrap/",
    "backend/src/aima_ugc/platform/",
    "backend/src/aima_ugc/modules/system/",
)
TOOLING_EXACT = (RUNTIME_EXACT - {"frontend/nginx.conf"}) | frozenset(
    {
        ".gitignore",
        ".python-version",
        ".node-version",
        ".uv-version",
        "scripts/setup_dev_environment.ps1",
        "scripts/setup_dev_environment.cmd",
        "scripts/dev/backend.py",
        "scripts/dev/frontend.py",
        "scripts/dev/local_runtime.py",
        "scripts/dev/configure_docker_desktop_mirrors.ps1",
    }
)
LINUX_SOURCE_BOOTSTRAP_EXACT = frozenset(
    {
        "backend/src/aima_ugc/adapters/persistence/postgres/system.py",
    }
)
RELEASE_EXACT = frozenset(
    {
        "Dockerfile",
        "compose.yaml",
        "compose.windows.yaml",
        "scripts/release/release_bundle.py",
        "scripts/deploy/start_compose.py",
        "scripts/deploy/stop_compose.py",
        "scripts/deploy/reset_keep_vehicle_catalog.sh",
        "scripts/release/build_local_release.ps1",
        "tests/unit/test_docker_build_sources.py",
        "tests/unit/test_release_workflow.py",
        "tests/unit/test_release_bundle.py",
        "tests/unit/test_compose_auto_scripts.py",
        "frontend/nginx.conf",
    }
)
DEV_HELPER_TARGETS = {
    "scripts/dev/compile_content_labeling.py": (
        "tests/unit/analysis/test_analysis_scheme_compilation.py",
    ),
    "scripts/dev/probe_collection_decision.py": (
        "tests/unit/collection/test_stage7_decision_probe.py",
    ),
}
REPOSITORY_QUALITY_EXACT = {
    "scripts/quality/actions_hygiene.py",
    "scripts/quality/archive_change_after_merge.py",
    "scripts/quality/check_agent_governance.py",
    "scripts/quality/check_change_completion.py",
    "scripts/quality/check_docs.py",
    "scripts/quality/check_docs_facts.py",
    "scripts/quality/check_pr_requirement_source.py",
    "scripts/quality/scan_secrets.py",
}
FULL_EXACT = {
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".uv-version",
    "compose.yaml",
    "compose.windows.yaml",
    "Dockerfile",
    "frontend/playwright.fullstack.config.ts",
}
FRONTEND_DEPENDENCY_AUDIT_EXACT = {
    "frontend/package.json",
    "frontend/package-lock.json",
    ".node-version",
}
PACKAGE_BUILD_EXACT = {
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".uv-version",
    "backend/src/aima_ugc/__init__.py",
}
FULL_PREFIXES = (
    "migrations/",
    "scripts/dev/",
    "scripts/release/",
)
CONTRACT_PREFIXES = (
    "contracts/",
    "backend/src/aima_ugc/contracts/",
    "frontend/src/generated/api/",
    "scripts/contracts/",
)
PERSISTENCE_PREFIXES = (
    "backend/src/aima_ugc/adapters/persistence/postgres/",
    "backend/src/aima_ugc/modules/ingestion/",
)
PERSISTENCE_EXACT = {"backend/src/aima_ugc/database_schema.py"}
FRONTEND_PREFIXES = ("frontend/",)
BACKEND_PREFIXES = ("backend/", "tests/unit/", "tests/api/", "tests/contracts/")
API_CONTRACT_EXACT = {"backend/src/aima_ugc/entrypoints/api_main.py"}
REPOSITORY_QUALITY_TEST_MARKERS = (
    "actions_hygiene",
    "agent_governance",
    "change_archive",
    "change_completion",
    "docs_facts",
    "docs_navigation",
    "issue_acceptance",
    "pr_requirement",
)
MIGRATION_COMPATIBILITY_TEST = "tests/integration/database/verify_migration_compatibility.py"


@dataclass(frozen=True)
class CiRequirements:
    """描述一次变更必须运行的 CI 层和专项证据。"""

    profile: str
    repository_required: bool
    repository_quality_required: bool
    backend_required: bool
    frontend_required: bool
    contract_required: bool
    postgres_required: bool
    fullstack_required: bool
    stack_smoke_required: bool
    report_font_required: bool
    frontend_audit_required: bool
    package_required: bool
    backend_targets: tuple[str, ...]
    frontend_unit_targets: tuple[str, ...]
    frontend_e2e_specs: tuple[str, ...]
    postgres_targets: tuple[str, ...]
    postgres_suites: tuple[str, ...]
    fullstack_specs: tuple[str, ...]
    template_required: bool = False
    configuration_required: bool = False
    template_risk: str = "none"
    runtime_required: bool = False
    tooling_linux_required: bool = False
    tooling_windows_required: bool = False
    release_required: bool = False
    reasons: tuple[str, ...] = ()


def _normalize_path(path: str) -> str:
    """把 Git 路径规范成仓库相对 POSIX 形式，不破坏点目录。"""
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_governance_path(path: str) -> bool:
    """判断路径是否只属于项目治理记录而不改变产品运行实现。"""
    return (
        path in GOVERNANCE_ONLY_EXACT
        or path.endswith("/AGENTS.md")
        or path.startswith(GOVERNANCE_ONLY_PREFIXES)
    )


def _is_docs_path(path: str) -> bool:
    """判断路径是否属于当前文档/文档图片的轻量变更集合。"""
    if path in DOCS_ONLY_EXACT or path.endswith("/README.md"):
        return True
    return path.startswith(DOCS_ONLY_PREFIXES) and Path(path).suffix.lower() in DOCS_ONLY_SUFFIXES


def _is_ci_self_path(path: str) -> bool:
    """CI 自身变化必须 fail closed，防止分类器错误把自己的证明责任跳掉。"""
    return path in CI_SELF_EXACT or path.startswith(".github/workflows/")


def _is_repository_quality_path(path: str) -> bool:
    """只对白名单中的仓库治理/文档质量检查器及其专属测试启用轻量质量证据。"""
    if path in REPOSITORY_QUALITY_EXACT:
        return True
    if not path.startswith("tests/unit/test_"):
        return False
    filename = Path(path).name
    return any(marker in filename for marker in REPOSITORY_QUALITY_TEST_MARKERS)


def _is_contract_path(path: str) -> bool:
    """识别公共机器 Contract 及直接 HTTP 生产者，确保生成物漂移检查不会被跳过。"""
    if path in API_CONTRACT_EXACT or path.startswith(CONTRACT_PREFIXES):
        return True
    if not path.startswith("backend/src/aima_ugc/"):
        return False
    return path.endswith("_http.py") or path.endswith("/http.py") or "/http/" in path


def _is_persistence_path(path: str) -> bool:
    """识别需要真实 PostgreSQL 语义证明的生产机器事实路径。"""
    if path in PERSISTENCE_EXACT or path.startswith(PERSISTENCE_PREFIXES):
        return True
    if not path.startswith("backend/src/aima_ugc/"):
        return False
    return path.endswith("/tables.py") or "/tables/" in path


def _is_report_font_path(path: str) -> bool:
    """判断本次 Python 证据是否真实覆盖 Word/DOCX/Reporting 渲染能力。"""
    lowered = path.lower()
    return (
        "/reporting/" in lowered
        or lowered.startswith("tests/unit/reporting/")
        or "word" in Path(lowered).name
        or "docx" in Path(lowered).name
    )


def _backend_targets_for_path(path: str) -> tuple[tuple[str, ...], bool]:
    """把已知后端 Owner 映射到直接单测；未知共享边界由调用方回退 all。"""
    if path.startswith(("tests/unit/", "tests/api/", "tests/contracts/")) and path.endswith(".py"):
        if Path(path).name == "conftest.py":
            return (), False
        return (path,), True

    domain_markers: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "/modules/analysis/",
            (
                "tests/unit/analysis",
                "tests/unit/content/test_stage12_analysis_planner.py",
                "tests/api/test_analysis_all_scope.py",
                "tests/api/test_analysis_runtime_capability.py",
                "tests/api/test_analysis_taxonomy.py",
            ),
        ),
        (
            "/modules/collection/",
            (
                "tests/unit/collection",
                "tests/api/test_stage8e_collection_runs.py",
                "tests/api/test_stage8f_collection_strategy.py",
            ),
        ),
        (
            "/modules/content/",
            (
                "tests/unit/content",
                "tests/api/test_content_relevance_review_api.py",
                "tests/api/test_stage8d_contents.py",
            ),
        ),
        (
            "/modules/ingestion/",
            (
                "tests/unit/ingestion",
                "tests/api/test_stage12_historical_imports.py",
                "tests/api/test_stage8b_imports.py",
                "tests/api/test_stage8c_import_batches.py",
            ),
        ),
        (
            "/modules/vehicles/",
            (
                "tests/unit/vehicles",
                "tests/api/test_brand_vehicle_stage2_contract.py",
            ),
        ),
    )
    for marker, targets in domain_markers:
        if marker in path:
            return targets, True
    return (), False


def _frontend_targets_for_path(path: str) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    """把已知前端 Feature 映射到 Unit/Browser Mock；共享未知路径回退 all。"""
    if path.startswith("frontend/tests/") and path.endswith(".spec.ts"):
        return (path,), (), True
    if path.startswith("frontend/e2e/") and path.endswith(".spec.ts"):
        return (), (path,), True

    mappings: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
        (
            "frontend/src/features/voice-plaza/",
            (
                "frontend/tests/analysis-all-scope.spec.ts",
                "frontend/tests/voice-plaza-design.spec.ts",
                "frontend/tests/voice-plaza-media-preview.spec.ts",
                "frontend/tests/voice-plaza.spec.ts",
            ),
            (
                "frontend/e2e/voice-plaza-design.spec.ts",
                "frontend/e2e/voice-plaza-media-carousel.spec.ts",
                "frontend/e2e/voice-plaza-review-regressions.spec.ts",
                "frontend/e2e/voice-plaza.spec.ts",
            ),
        ),
        (
            "frontend/src/features/workbench/",
            ("frontend/tests/workbench.spec.ts",),
            ("frontend/e2e/workbench.spec.ts",),
        ),
        (
            "frontend/src/features/admin-configuration/",
            (
                "frontend/tests/admin-configuration-design.spec.ts",
                "frontend/tests/admin-configuration-presentation.spec.ts",
                "frontend/tests/provider-concurrency-config.spec.ts",
            ),
            (
                "frontend/e2e/admin-configuration-figma.spec.ts",
                "frontend/e2e/admin-configuration-release2.spec.ts",
            ),
        ),
        (
            "frontend/src/features/task-center/",
            (
                "frontend/tests/task-center-api.spec.ts",
                "frontend/tests/task-center.spec.ts",
                "frontend/tests/task-progress-bar.spec.ts",
            ),
            ("frontend/e2e/task-center.spec.ts",),
        ),
        (
            "frontend/src/features/collection-strategy/",
            (
                "frontend/tests/collection-strategy-design.spec.ts",
                "frontend/tests/collection-strategy.spec.ts",
            ),
            (
                "frontend/e2e/collection-strategy-figma-geometry.spec.ts",
                "frontend/e2e/collection-strategy-figma-projection.spec.ts",
                "frontend/e2e/collection-strategy.spec.ts",
            ),
        ),
        (
            "frontend/src/features/collection-runtime/",
            (
                "frontend/tests/collection-runtime-design.spec.ts",
                "frontend/tests/collection-runtime-release2.spec.ts",
                "frontend/tests/collection-runtime.spec.ts",
            ),
            ("frontend/e2e/collection-runtime.spec.ts",),
        ),
    )
    for marker, unit_targets, e2e_specs in mappings:
        if path.startswith(marker):
            return unit_targets, e2e_specs, True

    return (), (), False


def _ordered_targets(targets: set[str], *, all_value: tuple[str, ...]) -> tuple[str, ...]:
    """稳定输出目标；出现 all 时保持 fail-closed 全量语义。"""
    if "all" in targets:
        return all_value
    return tuple(sorted(targets))


def _postgres_targets_for_path(path: str) -> tuple[str, ...]:
    """优先把明确叶子变化映射到可直接证明风险的 PostgreSQL 测试文件。"""
    exact: dict[str, tuple[str, ...]] = {
        "backend/src/aima_ugc/adapters/persistence/postgres/workbench.py": (
            "tests/integration/content/test_workbench_runtime.py",
            "tests/integration/content/test_workbench_scheme_bootstrap.py",
        ),
    }
    if path in exact:
        return exact[path]

    if path.startswith("tests/integration/") and path.endswith(".py"):
        if path == MIGRATION_COMPATIBILITY_TEST or Path(path).name == "conftest.py":
            return ()
        relative = path.removeprefix("tests/integration/")
        suite = relative.split("/", 1)[0]
        if suite in {
            "platform",
            "database",
            "jobs",
            "collection",
            "content",
            "ingestion",
            "vehicles",
            "reporting",
        }:
            return (path,)
    return ()


def _postgres_suites_for_path(path: str) -> tuple[str, ...]:
    """把共享 persistence 变化映射到最小充分 PostgreSQL suite；未知边界返回 all。"""
    if _postgres_targets_for_path(path):
        return ()
    if path in PERSISTENCE_EXACT:
        return POSTGRES_ALL
    if path == MIGRATION_COMPATIBILITY_TEST:
        return ("migration",)

    if path.startswith("tests/integration/"):
        relative = path.removeprefix("tests/integration/")
        suite = relative.split("/", 1)[0]
        if Path(path).name == "conftest.py":
            return POSTGRES_ALL
        if suite in {
            "platform",
            "database",
            "jobs",
            "collection",
            "content",
            "ingestion",
            "vehicles",
            "reporting",
        }:
            return ()
        return POSTGRES_ALL

    markers: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
        (("/postgres/historical_import",), ("content", "ingestion")),
        (("/modules/collection/", "/postgres/collection"), ("collection",)),
        (
            (
                "/modules/vehicles/",
                "/postgres/vehicles",
                "/postgres/brand_vehicle",
                "/postgres/content_reclassification",
            ),
            ("vehicles",),
        ),
        (("/modules/content/", "/postgres/content"), ("content",)),
        (
            ("/modules/ingestion/", "/postgres/ingestion", "/postgres/import"),
            ("content", "ingestion"),
        ),
        (("/modules/system/", "/postgres/system"), ("platform", "readiness", "database")),
        (("/jobs/", "/postgres/jobs"), ("jobs",)),
    )
    for path_markers, suites in markers:
        if any(marker in path for marker in path_markers):
            return suites
    return POSTGRES_ALL


def _fullstack_mapping_for_path(path: str) -> tuple[tuple[str, ...], bool]:
    """返回用户 Journey 对应 spec 与“该路径是否已被显式分类”。"""
    if path.startswith("frontend/e2e-fullstack/") and path.endswith(".spec.ts"):
        spec = Path(path).name
        return ((spec,) if spec in ALL_FULLSTACK_SPECS else FULLSTACK_ALL), True

    collection_markers = ("/collection/", "collection-plan", "collection_strategy")
    ingestion_markers = ("/ingestion/", "import", "historical")
    analysis_markers = ("/analysis/", "analysis")
    analysis_scheme_markers = (
        "analysis_scheme",
        "/analysis/schemes.py",
        "/analysis/scheme_tables.py",
    )
    content_markers = ("/content/", "relevance", "voice-plaza", "voice_plaza")
    administration_markers = (
        "/administration",
        "/vehicles/",
        "admin-configuration",
        "notification",
        "reporting",
    )

    if any(marker in path for marker in analysis_scheme_markers):
        return (
            (
                "admin-product-capabilities.spec.ts",
                "stage12-historical-analysis.spec.ts",
            ),
            True,
        )
    if any(marker in path for marker in administration_markers):
        return ("admin-product-capabilities.spec.ts",), True
    if any(marker in path for marker in collection_markers):
        return (
            (
                "collection-plan-search-config.spec.ts",
                "comment-supplement.spec.ts",
            ),
            True,
        )
    if any(marker in path for marker in ingestion_markers):
        return ("excel-import.spec.ts", "stage12-historical-analysis.spec.ts"), True
    if any(marker in path for marker in analysis_markers):
        return ("analysis-streaming.spec.ts", "stage12-historical-analysis.spec.ts"), True
    if any(marker in path for marker in content_markers):
        return ("manual-relevance-review.spec.ts",), True
    if "workbench" in path:
        return ("analysis-streaming.spec.ts",), True
    if path.startswith(
        (
            "backend/src/aima_ugc/platform/",
            "backend/src/aima_ugc/adapters/",
            "tests/unit/",
            "tests/api/",
            "tests/contracts/",
        )
    ):
        return (), True
    return (), False


def _fullstack_specs_for_path(path: str) -> tuple[str, ...]:
    """兼容调用者，仅返回已经显式分类的 Real Full-stack spec 集合。"""
    return _fullstack_mapping_for_path(path)[0]


def _is_unmapped_user_journey_path(path: str) -> bool:
    """识别需要 fail-closed 的未知用户入口，而不是把任意技术文件都升级为 Full-stack。"""
    if path.startswith("frontend/src/features/"):
        return not _fullstack_mapping_for_path(path)[1]
    if path.startswith("backend/src/aima_ugc/bootstrap/") and (
        path.endswith("_http.py") or path.endswith("/http.py") or "/http/" in path
    ):
        return not _fullstack_mapping_for_path(path)[1]
    return False


def _ordered_specs(specs: set[str]) -> tuple[str, ...]:
    """按正式 Full-stack suite 的固定顺序输出 spec；`all` 优先表示整个目录。"""
    if "all" in specs:
        return FULLSTACK_ALL
    return tuple(spec for spec in ALL_FULLSTACK_SPECS if spec in specs)


def _ordered_postgres_targets(targets: set[str]) -> tuple[str, ...]:
    """稳定输出精确 PostgreSQL 测试目标，便于 Workflow 复现与审计。"""
    return tuple(sorted(targets))


def _ordered_postgres_suites(suites: set[str]) -> tuple[str, ...]:
    """按 PostgreSQL Job 固定顺序输出 suite；`all` 表示不可安全收窄。"""
    if "all" in suites:
        return POSTGRES_ALL
    return tuple(suite for suite in ALL_POSTGRES_SUITES if suite in suites)


def _full_requirements() -> CiRequirements:
    """返回 fail-closed 的完整 CI 责任，用于未知路径、CI 自身和高风险基础设施变化。"""
    return CiRequirements(
        profile="full",
        repository_required=True,
        repository_quality_required=True,
        backend_required=True,
        frontend_required=True,
        contract_required=True,
        postgres_required=True,
        fullstack_required=True,
        stack_smoke_required=True,
        report_font_required=True,
        frontend_audit_required=True,
        package_required=True,
        backend_targets=BACKEND_ALL,
        frontend_unit_targets=FRONTEND_ALL,
        frontend_e2e_specs=FRONTEND_ALL,
        postgres_targets=(),
        postgres_suites=POSTGRES_ALL,
        fullstack_specs=FULLSTACK_ALL,
        template_required=True,
        configuration_required=True,
        runtime_required=True,
        tooling_linux_required=True,
        tooling_windows_required=True,
        release_required=True,
        reasons=("CI/共享基础设施/未知路径要求完整证明；不由变更后的控制面免除自己。",),
    )


def classify_requirements(
    paths: Iterable[str],
    *,
    template_changes: dict[str, tuple[str | None, str | None]] | None = None,
) -> CiRequirements:
    """汇总 changed paths；只有明确白名单能降低成本，未知或高风险路径始终回退 full。"""
    normalized = tuple(path for raw in paths if (path := _normalize_path(raw)))
    if not normalized:
        return _full_requirements()

    templates = tuple(path for path in normalized if path in ENV_TEMPLATES)
    if templates:
        remaining = tuple(path for path in normalized if path not in ENV_TEMPLATES)
        requirements = classify_requirements(remaining or ("README.md",))
        risk, deployment = _template_risk(templates, template_changes)
        if risk == "unknown":
            return replace(_full_requirements(), template_risk=risk)
        return replace(
            requirements,
            profile=requirements.profile
            if remaining and requirements.repository_required
            else "configuration",
            template_required=True,
            configuration_required=risk != "comments" or requirements.configuration_required,
            template_risk=risk,
            runtime_required=requirements.runtime_required or deployment,
            tooling_windows_required=requirements.tooling_windows_required
            or deployment
            or ("env.local.example" in templates and risk != "comments"),
            release_required=requirements.release_required or deployment,
            reasons=(
                *requirements.reasons,
                f"env 模板风险={risk}；配置解析/打包/渲染承担模板责任。",
            ),
        )

    product_paths = tuple(
        path for path in normalized if not _is_docs_path(path) and not _is_governance_path(path)
    )
    if not product_paths:
        profile = (
            "governance_only"
            if any(_is_governance_path(path) for path in normalized)
            else "docs_only"
        )
        return CiRequirements(
            profile=profile,
            repository_required=False,
            repository_quality_required=False,
            backend_required=False,
            frontend_required=False,
            contract_required=False,
            postgres_required=False,
            fullstack_required=False,
            stack_smoke_required=False,
            report_font_required=False,
            frontend_audit_required=False,
            package_required=False,
            backend_targets=(),
            frontend_unit_targets=(),
            frontend_e2e_specs=(),
            postgres_targets=(),
            postgres_suites=(),
            fullstack_specs=(),
        )

    repository_quality_required = False
    backend_required = False
    frontend_required = False
    contract_required = False
    postgres_required = False
    report_font_required = False
    frontend_audit_required = any(path in FRONTEND_DEPENDENCY_AUDIT_EXACT for path in product_paths)
    package_required = any(path in PACKAGE_BUILD_EXACT for path in product_paths)
    backend_targets: set[str] = set()
    frontend_unit_targets: set[str] = set()
    frontend_e2e_specs: set[str] = set()
    backend_has_unmapped = False
    frontend_has_unmapped = False
    postgres_targets: set[str] = set()
    postgres_suites: set[str] = set()
    fullstack_specs: set[str] = set()
    journey_specs: set[str] = set()
    has_unmapped_user_journey = False
    kinds: set[str] = set()

    for path in product_paths:
        if path in DEV_HELPER_TARGETS:
            backend_required = True
            backend_targets.update(DEV_HELPER_TARGETS[path])
            kinds.add("backend")
            continue
        if _is_ci_self_path(path) or path in FULL_EXACT or path.startswith(FULL_PREFIXES):
            return _full_requirements()

        if _is_repository_quality_path(path):
            repository_quality_required = True
            kinds.add("repository_quality")
            continue

        report_font_required = report_font_required or _is_report_font_path(path)

        if path.startswith("frontend/e2e-fullstack/") and path.endswith(".spec.ts"):
            frontend_required = True
            frontend_has_unmapped = True
            fullstack_specs.update(_fullstack_specs_for_path(path))
            kinds.add("frontend")
            continue

        if path.startswith("frontend/e2e-fullstack/"):
            frontend_required = True
            frontend_has_unmapped = True
            fullstack_specs.update(FULLSTACK_ALL)
            kinds.add("frontend")
            continue

        if _is_contract_path(path):
            backend_required = True
            frontend_required = True
            contract_required = True
            backend_targets.update(BACKEND_ALL)
            frontend_unit_targets.update(FRONTEND_ALL)
            frontend_e2e_specs.update(FRONTEND_ALL)
            if path == API_CONTRACT_EXACT or path.startswith(CONTRACT_PREFIXES):
                fullstack_specs.update(FULLSTACK_ALL)
            else:
                mapped_specs, mapped = _fullstack_mapping_for_path(path)
                if mapped:
                    fullstack_specs.update(mapped_specs)
                else:
                    fullstack_specs.update(FULLSTACK_ALL)
            kinds.add("contract")
            continue

        if path.startswith("tests/integration/"):
            backend_required = True
            backend_has_unmapped = True
            postgres_required = True
            postgres_targets.update(_postgres_targets_for_path(path))
            postgres_suites.update(_postgres_suites_for_path(path))
            kinds.add("persistence")
            continue

        if _is_persistence_path(path):
            backend_required = True
            backend_direct, backend_mapped = _backend_targets_for_path(path)
            if backend_mapped:
                backend_targets.update(backend_direct)
            else:
                backend_has_unmapped = True
            postgres_required = True
            targets = _postgres_targets_for_path(path)
            suites = _postgres_suites_for_path(path)
            postgres_targets.update(targets)
            postgres_suites.update(suites)
            mapped_specs = _fullstack_specs_for_path(path)
            if mapped_specs:
                fullstack_specs.update(mapped_specs)
            elif not targets and suites == POSTGRES_ALL:
                fullstack_specs.update(FULLSTACK_ALL)
            kinds.add("persistence")
            continue

        if path.startswith(FRONTEND_PREFIXES):
            frontend_required = True
            unit_targets, e2e_specs, frontend_mapped = _frontend_targets_for_path(path)
            if frontend_mapped:
                frontend_unit_targets.update(unit_targets)
                frontend_e2e_specs.update(e2e_specs)
            else:
                frontend_has_unmapped = True
            journey_specs.update(_fullstack_specs_for_path(path))
            has_unmapped_user_journey = has_unmapped_user_journey or _is_unmapped_user_journey_path(
                path
            )
            kinds.add("frontend")
            continue

        if path.startswith(BACKEND_PREFIXES):
            backend_required = True
            backend_direct, backend_mapped = _backend_targets_for_path(path)
            if backend_mapped:
                backend_targets.update(backend_direct)
            else:
                backend_has_unmapped = True
            journey_specs.update(_fullstack_specs_for_path(path))
            has_unmapped_user_journey = has_unmapped_user_journey or _is_unmapped_user_journey_path(
                path
            )
            kinds.add("backend")
            continue

        return _full_requirements()

    if "contract" in kinds:
        profile = "contract"
    elif "persistence" in kinds and kinds <= {"persistence", "repository_quality"}:
        profile = "persistence"
    elif kinds == {"repository_quality"}:
        profile = "repository_quality"
    elif kinds <= {"frontend", "repository_quality"} and "frontend" in kinds:
        profile = "frontend_only"
    elif kinds <= {"backend", "repository_quality"} and "backend" in kinds:
        profile = "backend_only"
    else:
        profile = "cross_component"

    if frontend_required and backend_required and not contract_required:
        if has_unmapped_user_journey:
            fullstack_specs.update(FULLSTACK_ALL)
        else:
            fullstack_specs.update(journey_specs)

    if backend_required and (backend_has_unmapped or not backend_targets):
        backend_targets.update(BACKEND_ALL)
    if frontend_required and frontend_has_unmapped:
        frontend_unit_targets.update(FRONTEND_ALL)
        frontend_e2e_specs.update(FRONTEND_ALL)

    selected_backend_targets = _ordered_targets(backend_targets, all_value=BACKEND_ALL)
    selected_frontend_unit_targets = _ordered_targets(frontend_unit_targets, all_value=FRONTEND_ALL)
    selected_frontend_e2e_specs = _ordered_targets(frontend_e2e_specs, all_value=FRONTEND_ALL)
    selected_postgres_targets = _ordered_postgres_targets(postgres_targets)
    selected_postgres_suites = _ordered_postgres_suites(postgres_suites)
    if postgres_required and not selected_postgres_targets and not selected_postgres_suites:
        selected_postgres_suites = POSTGRES_ALL
    selected_specs = _ordered_specs(fullstack_specs)
    return CiRequirements(
        profile=profile,
        repository_required=True,
        repository_quality_required=repository_quality_required,
        backend_required=backend_required,
        frontend_required=frontend_required,
        contract_required=contract_required,
        postgres_required=postgres_required,
        fullstack_required=bool(selected_specs),
        stack_smoke_required=False,
        report_font_required=report_font_required,
        frontend_audit_required=frontend_audit_required,
        package_required=package_required,
        backend_targets=selected_backend_targets,
        frontend_unit_targets=selected_frontend_unit_targets,
        frontend_e2e_specs=selected_frontend_e2e_specs,
        postgres_targets=selected_postgres_targets,
        postgres_suites=selected_postgres_suites,
        fullstack_specs=selected_specs,
        runtime_required=any(
            path in RUNTIME_EXACT
            or path.startswith(RUNTIME_PREFIXES)
            or path == "backend/src/aima_ugc/adapters/persistence/postgres/system.py"
            for path in normalized
        ),
        tooling_linux_required=any(
            path in TOOLING_EXACT
            or path in LINUX_SOURCE_BOOTSTRAP_EXACT
            or path.startswith(RUNTIME_PREFIXES)
            for path in normalized
        ),
        tooling_windows_required=any(
            path in TOOLING_EXACT or path.startswith(RUNTIME_PREFIXES) for path in normalized
        ),
        release_required=any(path in RELEASE_EXACT for path in normalized),
        reasons=(f"{profile} 按已知消费者选择直接证据；未知边界仍回退 full。",),
    )


def _template_risk(
    paths: tuple[str, ...], changes: dict[str, tuple[str | None, str | None]] | None
) -> tuple[str, bool]:
    """只分析正式模板的声明变化；缺失或删除无法证明为低风险。"""
    parse = runpy.run_path(str(Path(__file__).with_name("check_env_templates.py")))[
        "parse_template"
    ]
    risk = "comments"
    deployment = False
    for path in paths:
        before, after = (changes or {}).get(path, (None, None))
        if before is None or after is None:
            return "unknown", True
        try:
            # 引号/转义/插值影响 Compose 消费语义，风险比较不得先去掉外引号。
            old = parse(before, path, legacy_duplicates=True, preserve_syntax=True)
            new = parse(after, path, preserve_syntax=True)
        except ValueError:
            return "unknown", True
        keys = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
        try:
            parse(before, path)
        except ValueError:
            # 旧模板后值覆盖是历史事实；去重仍要求配置验证，不能把修复判作未知全量。
            risk = "values"
        if keys and risk == "comments":
            risk = "values"
        if any(
            key.startswith(
                (
                    "AIMA_FEISHU_",
                    "AIMA_TIKHUB_",
                    "AIMA_LLM_",
                    "AIMA_HTTP_",
                    "AIMA_DOCKER_",
                    "AIMA_BUILD_",
                    "AIMA_HOST_",
                    "AIMA_HISTORICAL_",
                    "AIMA_DB_",
                    "AIMA_IMAGE_",
                )
            )
            or "SECRET" in key
            or "KEY" in key
            for key in keys
        ):
            risk = "sensitive"
        deployment = deployment or any(
            key.startswith(
                (
                    "AIMA_HTTP_",
                    "AIMA_DOCKER_",
                    "AIMA_BUILD_",
                    "AIMA_HOST_",
                    "AIMA_HISTORICAL_",
                    "AIMA_DB_",
                    "AIMA_IMAGE_",
                )
            )
            for key in keys
        )
    return risk, deployment


def classify_paths(paths: Iterable[str]) -> str:
    """兼容旧调用者，仅返回新证明责任模型计算出的 profile。"""
    return classify_requirements(paths).profile


def _git_bytes(arguments: list[str], *, root: Path | None = None) -> bytes:
    """读取 Git 事实；无法证明范围时明确失败，不能把错误当成空变更。"""
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError("Git 对象/基线查询失败；请确认 ref 与完整历史（fetch-depth: 0）") from exc
    return completed.stdout


def scope_base(
    base: str, head: str, *, comparison: str = "merge-base", root: Path | None = None
) -> str:
    """PR 使用唯一 merge-base；push 使用显式两个提交，不能混用执行树和影响范围。"""
    if not base or not head or set(base) == {"0"}:
        raise ValueError("Git 基线/目标不能为空或零 SHA；定时安全网请显式使用 --full")
    for ref in (base, head):
        _git_bytes(["rev-parse", "--verify", f"{ref}^{{commit}}"], root=root)
    if comparison == "direct":
        return base
    if _git_bytes(["rev-parse", "--is-shallow-repository"], root=root).strip() == b"true":
        raise ValueError("PR merge-base 无法在 shallow repository 证明完整；请使用 fetch-depth: 0")
    bases = _git_bytes(["merge-base", "--all", base, head], root=root).decode().splitlines()
    if len(bases) != 1:
        raise ValueError(f"Git merge-base 必须唯一，实际 {len(bases)} 个；禁止猜测影响范围")
    return bases[0]


def changed_scope(
    base: str,
    head: str,
    *,
    comparison: str = "merge-base",
    root: Path | None = None,
    include_worktree: bool = False,
) -> list[str]:
    """统一恢复分支自身与开发期 staged/unstaged/untracked 路径。"""
    start = scope_base(base, head, comparison=comparison, root=root)
    arguments = ["diff", "--no-renames", "--name-only", "-z", start]
    worktree = include_worktree and head == "HEAD"
    if not worktree:
        arguments.append(head)
    raw = _git_bytes(arguments, root=root)
    if worktree:
        raw += _git_bytes(["ls-files", "--others", "--exclude-standard", "-z"], root=root)
    return list(
        dict.fromkeys(
            item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item
        )
    )


def _changed_paths(base: str, head: str) -> list[str]:
    """兼容既有内部入口，默认采用真实 PR 三点语义。"""
    return changed_scope(base, head)


def normalize_available_targets(requirements: CiRequirements, *, root: Path) -> CiRequirements:
    """按实际 checkout/worktree 收敛可执行证据；删除目标只能升级 Owner 责任。"""
    missing: set[str] = set()

    def exists(target: str) -> bool:
        available = target == "all" or (root / target).exists()
        if not available:
            missing.add(target)
        return available

    backend: set[str] = set()
    for target in requirements.backend_targets:
        if exists(target):
            backend.add(target)
            continue
        owner = Path(target).parent
        # 不跨过 Unit/API/Contract Owner 根，防止把普通单测扩成数据库测试。
        while owner.as_posix().startswith(("tests/unit", "tests/api", "tests/contracts")):
            if (root / owner).is_dir() and any((root / owner).rglob("test_*.py")):
                backend.add(owner.as_posix())
                break
            owner = owner.parent
        else:
            backend.add("all")
    ordered_backend = _ordered_targets(backend, all_value=BACKEND_ALL)
    # Owner 目录已经覆盖其叶子，避免 rename 后新叶子和整个 Owner 重复执行。
    backend_targets = tuple(
        target
        for target in ordered_backend
        if not any(target.startswith(other + "/") for other in ordered_backend if other != target)
    )

    def frontend_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
        return targets if all(exists(target) for target in targets) else FRONTEND_ALL

    unit = frontend_targets(requirements.frontend_unit_targets)
    browser = frontend_targets(requirements.frontend_e2e_specs)
    postgres_targets: set[str] = set()
    postgres_suites = set(requirements.postgres_suites)
    for target in requirements.postgres_targets:
        if exists(target):
            postgres_targets.add(target)
            continue
        relative = target.removeprefix("tests/integration/")
        suite = relative.split("/", 1)[0]
        owner = root / "tests/integration" / suite
        if suite in ALL_POSTGRES_SUITES and owner.is_dir() and any(owner.rglob("test_*.py")):
            postgres_suites.add(suite)
        else:
            postgres_suites.add("all")
    postgres_targets = {
        target
        for target in postgres_targets
        if "all" not in postgres_suites
        and not any(target.startswith(f"tests/integration/{suite}/") for suite in postgres_suites)
    }
    fullstack = requirements.fullstack_specs
    if any(spec != "all" and not exists(f"frontend/e2e-fullstack/{spec}") for spec in fullstack):
        fullstack = FULLSTACK_ALL
    return replace(
        requirements,
        backend_targets=backend_targets,
        frontend_unit_targets=unit,
        frontend_e2e_specs=browser,
        postgres_targets=_ordered_postgres_targets(postgres_targets),
        postgres_suites=_ordered_postgres_suites(postgres_suites),
        fullstack_specs=fullstack,
        reasons=(
            *requirements.reasons,
            "缺失目标按实际 checkout 升级 Owner 证据：" + ", ".join(sorted(missing)),
        )
        if missing
        else requirements.reasons,
    )


def classify_scope(
    base: str,
    head: str,
    *,
    comparison: str = "merge-base",
    root: Path | None = None,
    include_worktree: bool = False,
) -> tuple[CiRequirements, list[str]]:
    """范围和模板内容读取采用同一基线、目标与 worktree 事实。"""
    paths = changed_scope(
        base, head, comparison=comparison, root=root, include_worktree=include_worktree
    )
    start = scope_base(base, head, comparison=comparison, root=root)
    changes: dict[str, tuple[str | None, str | None]] = {}
    for path in paths:
        if path not in ENV_TEMPLATES:
            continue

        def read(ref: str, target_path: str = path) -> str | None:
            try:
                return _git_bytes(["show", f"{ref}:{target_path}"], root=root).decode("utf-8")
            except ValueError:
                return None

        before = read(start)
        if include_worktree and head == "HEAD":
            target = (root or Path.cwd()) / path
            after = target.read_text(encoding="utf-8") if target.is_file() else None
        else:
            after = read(head)
        changes[path] = before, after
    checkout_root = root or Path(_git_bytes(["rev-parse", "--show-toplevel"]).decode().strip())
    requirements = classify_requirements(paths, template_changes=changes)
    return normalize_available_targets(requirements, root=checkout_root), paths


def _bool_output(value: bool) -> str:
    """把 Python 布尔值固定转换为 GitHub Actions 可比较的小写字符串。"""
    return "true" if value else "false"


def _write_github_output(path: Path, requirements: CiRequirements, changed_count: int) -> None:
    """把风险层、PostgreSQL suites 和 selected Full-stack specs 写入 Actions 输出。"""
    values = {
        "profile": requirements.profile,
        "repository_required": _bool_output(requirements.repository_required),
        "repository_quality_required": _bool_output(requirements.repository_quality_required),
        "backend_required": _bool_output(requirements.backend_required),
        "frontend_required": _bool_output(requirements.frontend_required),
        "contract_required": _bool_output(requirements.contract_required),
        "postgres_required": _bool_output(requirements.postgres_required),
        "fullstack_required": _bool_output(requirements.fullstack_required),
        "stack_smoke_required": _bool_output(requirements.stack_smoke_required),
        "report_font_required": _bool_output(requirements.report_font_required),
        "frontend_audit_required": _bool_output(requirements.frontend_audit_required),
        "package_required": _bool_output(requirements.package_required),
        "backend_targets": " ".join(requirements.backend_targets),
        "frontend_unit_targets": " ".join(requirements.frontend_unit_targets),
        "frontend_e2e_specs": " ".join(requirements.frontend_e2e_specs),
        "postgres_targets": " ".join(requirements.postgres_targets),
        "postgres_suites": " ".join(requirements.postgres_suites),
        "fullstack_specs": " ".join(requirements.fullstack_specs),
        "changed_count": str(changed_count),
    }
    for key in (
        "template_required",
        "configuration_required",
        "runtime_required",
        "tooling_linux_required",
        "tooling_windows_required",
        "release_required",
    ):
        values[key] = _bool_output(getattr(requirements, key))
    values["template_risk"] = requirements.template_risk
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def _requirements_json(requirements: CiRequirements, changed_paths: list[str]) -> str:
    """输出开发期/CI 共用的机器可读分类结果。"""
    payload = {
        **asdict(requirements),
        "profile": requirements.profile,
        "repository_required": requirements.repository_required,
        "repository_quality_required": requirements.repository_quality_required,
        "backend_required": requirements.backend_required,
        "frontend_required": requirements.frontend_required,
        "contract_required": requirements.contract_required,
        "postgres_required": requirements.postgres_required,
        "fullstack_required": requirements.fullstack_required,
        "stack_smoke_required": requirements.stack_smoke_required,
        "report_font_required": requirements.report_font_required,
        "frontend_audit_required": requirements.frontend_audit_required,
        "package_required": requirements.package_required,
        "backend_targets": list(requirements.backend_targets),
        "frontend_unit_targets": list(requirements.frontend_unit_targets),
        "frontend_e2e_specs": list(requirements.frontend_e2e_specs),
        "postgres_targets": list(requirements.postgres_targets),
        "postgres_suites": list(requirements.postgres_suites),
        "fullstack_specs": list(requirements.fullstack_specs),
        "changed_count": len(changed_paths),
        "changed_paths": changed_paths,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def main() -> int:
    """从 Git diff 计算 CI 证明责任，并可输出给 GitHub Actions。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="", help="变更基线 commit SHA")
    parser.add_argument("--head", default="HEAD", help="变更目标 commit SHA")
    parser.add_argument("--comparison", choices=("merge-base", "direct"), default="merge-base")
    parser.add_argument("--full", action="store_true", help="显式定时全量安全网")
    parser.add_argument("--github-output", type=Path, help="可选 GITHUB_OUTPUT 文件")
    parser.add_argument("--json", action="store_true", help="仅输出机器可读 JSON")
    args = parser.parse_args()

    if args.full:
        requirements = _full_requirements()
        changed_paths = []
        changed_count = 0
    else:
        try:
            requirements, changed_paths = classify_scope(
                args.base, args.head, comparison=args.comparison
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        changed_count = len(changed_paths)

    if args.json:
        print(_requirements_json(requirements, changed_paths))
    else:
        if changed_count == 0 and requirements.profile == "full":
            print("无法可靠读取变更范围，保守使用 full CI profile。")
        print(
            "CI profile="
            f"{requirements.profile}; changed_count={changed_count}; "
            f"repository_quality={requirements.repository_quality_required}; "
            f"backend={requirements.backend_required}; frontend={requirements.frontend_required}; "
            f"contract={requirements.contract_required}; "
            f"postgres={requirements.postgres_required}; "
            f"fullstack={requirements.fullstack_required}"
        )
        for changed_path in changed_paths:
            print(f"- {changed_path}")
        if requirements.backend_targets:
            print("Backend targets: " + " ".join(requirements.backend_targets))
        if requirements.frontend_unit_targets:
            print("Frontend unit targets: " + " ".join(requirements.frontend_unit_targets))
        if requirements.frontend_e2e_specs:
            print("Frontend browser specs: " + " ".join(requirements.frontend_e2e_specs))
        if requirements.postgres_targets:
            print("PostgreSQL targets: " + " ".join(requirements.postgres_targets))
        if requirements.postgres_suites:
            print("PostgreSQL suites: " + " ".join(requirements.postgres_suites))
        if requirements.fullstack_specs:
            print("Full-stack specs: " + " ".join(requirements.fullstack_specs))

    if args.github_output is not None:
        _write_github_output(args.github_output, requirements, changed_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
