"""按变更路径保守计算 AIMA CI 需要保留的独立证明责任。"""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ALL_FULLSTACK_SPECS = (
    "collection-plan-search-config.spec.ts",
    "excel-import.spec.ts",
    "manual-relevance-review.spec.ts",
    "stage12-historical-analysis.spec.ts",
)

DOCS_ONLY_EXACT = {"README.md"}
GOVERNANCE_ONLY_EXACT = {"AGENTS.md"}
DOCS_ONLY_PREFIXES = ("docs/",)
DOCS_ONLY_SUFFIXES = {".md", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
GOVERNANCE_ONLY_PREFIXES = ("changes/", ".agents/")

CI_SELF_EXACT = {
    ".github/workflows/ci.yml",
    ".github/workflows/fullstack.yml",
    "scripts/quality/classify_ci_scope.py",
    "tests/unit/test_ci_scope.py",
}
FULL_EXACT = {
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".uv-version",
    "compose.yaml",
    "compose.windows.yaml",
    "Dockerfile",
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


@dataclass(frozen=True)
class CiRequirements:
    """描述一次变更必须运行的 CI 层和 Real Full-stack Golden Path。"""

    profile: str
    repository_required: bool
    backend_required: bool
    frontend_required: bool
    contract_required: bool
    postgres_required: bool
    fullstack_required: bool
    stack_smoke_required: bool
    fullstack_specs: tuple[str, ...]


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


def _fullstack_specs_for_path(path: str) -> tuple[str, ...]:
    """把高价值真实用户链路映射到当前四条 Golden Path；无法精确归属时返回全集。"""
    if path.startswith("frontend/e2e-fullstack/") and path.endswith(".spec.ts"):
        spec = Path(path).name
        return (spec,) if spec in ALL_FULLSTACK_SPECS else ALL_FULLSTACK_SPECS

    collection_markers = ("/collection/", "collection-plan", "collection_strategy")
    ingestion_markers = ("/ingestion/", "import", "historical")
    analysis_markers = ("/analysis/", "analysis")
    content_markers = ("/content/", "relevance")

    if any(marker in path for marker in collection_markers):
        return ("collection-plan-search-config.spec.ts",)
    if any(marker in path for marker in ingestion_markers):
        return ("excel-import.spec.ts", "stage12-historical-analysis.spec.ts")
    if any(marker in path for marker in analysis_markers):
        return ("stage12-historical-analysis.spec.ts",)
    if any(marker in path for marker in content_markers):
        return ("manual-relevance-review.spec.ts",)
    return ALL_FULLSTACK_SPECS


def _ordered_specs(specs: set[str]) -> tuple[str, ...]:
    """按正式 Full-stack suite 的固定顺序输出 spec，避免集合顺序造成 CI 漂移。"""
    return tuple(spec for spec in ALL_FULLSTACK_SPECS if spec in specs)


def _full_requirements() -> CiRequirements:
    """返回 fail-closed 的完整 CI 责任，用于未知路径、CI 自身和高风险基础设施变化。"""
    return CiRequirements(
        profile="full",
        repository_required=True,
        backend_required=True,
        frontend_required=True,
        contract_required=True,
        postgres_required=True,
        fullstack_required=True,
        stack_smoke_required=True,
        fullstack_specs=ALL_FULLSTACK_SPECS,
    )


def classify_requirements(paths: Iterable[str]) -> CiRequirements:
    """汇总 changed paths；只有明确白名单能降低成本，未知或高风险路径始终回退 full。"""
    normalized = tuple(path for raw in paths if (path := _normalize_path(raw)))
    if not normalized:
        return _full_requirements()

    product_paths = tuple(
        path for path in normalized if not _is_docs_path(path) and not _is_governance_path(path)
    )
    if not product_paths:
        profile = "governance_only" if any(_is_governance_path(path) for path in normalized) else "docs_only"
        return CiRequirements(
            profile=profile,
            repository_required=False,
            backend_required=False,
            frontend_required=False,
            contract_required=False,
            postgres_required=False,
            fullstack_required=False,
            stack_smoke_required=False,
            fullstack_specs=(),
        )

    backend_required = False
    frontend_required = False
    contract_required = False
    postgres_required = False
    fullstack_specs: set[str] = set()
    kinds: set[str] = set()

    for path in product_paths:
        if _is_ci_self_path(path) or path in FULL_EXACT or path.startswith(FULL_PREFIXES):
            return _full_requirements()

        if path.startswith("frontend/e2e-fullstack/") and path.endswith(".spec.ts"):
            frontend_required = True
            fullstack_specs.update(_fullstack_specs_for_path(path))
            kinds.add("frontend")
            continue

        if _is_contract_path(path):
            backend_required = True
            frontend_required = True
            contract_required = True
            fullstack_specs.update(ALL_FULLSTACK_SPECS)
            kinds.add("contract")
            continue

        if path.startswith("tests/integration/"):
            backend_required = True
            postgres_required = True
            kinds.add("persistence")
            continue

        if _is_persistence_path(path):
            backend_required = True
            postgres_required = True
            fullstack_specs.update(_fullstack_specs_for_path(path))
            kinds.add("persistence")
            continue

        if path.startswith(FRONTEND_PREFIXES):
            frontend_required = True
            kinds.add("frontend")
            continue

        if path.startswith(BACKEND_PREFIXES):
            backend_required = True
            kinds.add("backend")
            continue

        return _full_requirements()

    if "contract" in kinds:
        profile = "contract"
    elif "persistence" in kinds and "frontend" not in kinds:
        profile = "persistence"
    elif kinds == {"frontend"}:
        profile = "frontend_only"
    elif kinds == {"backend"}:
        profile = "backend_only"
    else:
        profile = "cross_component"

    if frontend_required and backend_required and not contract_required:
        fullstack_specs.update(ALL_FULLSTACK_SPECS)

    selected_specs = _ordered_specs(fullstack_specs)
    return CiRequirements(
        profile=profile,
        repository_required=True,
        backend_required=backend_required,
        frontend_required=frontend_required,
        contract_required=contract_required,
        postgres_required=postgres_required,
        fullstack_required=bool(selected_specs),
        stack_smoke_required=False,
        fullstack_specs=selected_specs,
    )


def classify_paths(paths: Iterable[str]) -> str:
    """兼容旧调用者，仅返回新证明责任模型计算出的 profile。"""
    return classify_requirements(paths).profile


def _changed_paths(base: str, head: str) -> list[str] | None:
    """读取两个提交间全部路径；关闭 rename detection 以同时保留旧/新路径风险。"""
    if not base or not head or set(base) == {"0"}:
        return None
    try:
        completed = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", base, head],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return None
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    ]


def _bool_output(value: bool) -> str:
    """把 Python 布尔值固定转换为 GitHub Actions 可比较的小写字符串。"""
    return "true" if value else "false"


def _write_github_output(path: Path, requirements: CiRequirements, changed_count: int) -> None:
    """把风险层和 selected Full-stack specs 写入 GitHub Actions 输出文件。"""
    values = {
        "profile": requirements.profile,
        "repository_required": _bool_output(requirements.repository_required),
        "backend_required": _bool_output(requirements.backend_required),
        "frontend_required": _bool_output(requirements.frontend_required),
        "contract_required": _bool_output(requirements.contract_required),
        "postgres_required": _bool_output(requirements.postgres_required),
        "fullstack_required": _bool_output(requirements.fullstack_required),
        "stack_smoke_required": _bool_output(requirements.stack_smoke_required),
        "fullstack_specs": " ".join(requirements.fullstack_specs),
        "changed_count": str(changed_count),
    }
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    """从 Git diff 计算 CI 证明责任，并可输出给 GitHub Actions。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="变更基线 commit SHA")
    parser.add_argument("--head", required=True, help="变更目标 commit SHA")
    parser.add_argument("--github-output", type=Path, help="可选 GITHUB_OUTPUT 文件")
    args = parser.parse_args()

    changed_paths = _changed_paths(args.base, args.head)
    if changed_paths is None:
        requirements = _full_requirements()
        changed_count = 0
        print("无法可靠读取变更范围，保守使用 full CI profile。")
    else:
        requirements = classify_requirements(changed_paths)
        changed_count = len(changed_paths)
        print(
            "CI profile="
            f"{requirements.profile}; changed_count={changed_count}; "
            f"backend={requirements.backend_required}; frontend={requirements.frontend_required}; "
            f"contract={requirements.contract_required}; postgres={requirements.postgres_required}; "
            f"fullstack={requirements.fullstack_required}"
        )
        for changed_path in changed_paths:
            print(f"- {changed_path}")
        if requirements.fullstack_specs:
            print("Full-stack specs: " + " ".join(requirements.fullstack_specs))

    if args.github_output is not None:
        _write_github_output(args.github_output, requirements, changed_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
