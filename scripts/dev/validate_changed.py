"""按 AIMA 唯一 CI classifier 生成并可执行开发期 changed-scope preflight。"""

from __future__ import annotations

import argparse
import runpy
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER_PATH = ROOT / "scripts" / "quality" / "classify_ci_scope.py"
_CLASSIFIER = runpy.run_path(str(CLASSIFIER_PATH))
classify_requirements = _CLASSIFIER["classify_requirements"]
_changed_paths = _CLASSIFIER["_changed_paths"]


def _resolve_revision(value: str) -> str:
    """解析 Git revision，失败时保留 Git 原始错误并停止。"""
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", value],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _print_targets(label: str, targets: tuple[str, ...]) -> None:
    """以稳定文本输出某一层选中的直接目标。"""
    rendered = " ".join(targets) if targets else "not_required"
    print(f"{label}: {rendered}")


def _run(command: list[str]) -> None:
    """执行一个已规划的本地验证命令，并在失败时立即停止。"""
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _run_backend(requirements: Any) -> None:
    """执行 Backend 静态门禁和 classifier 选择的直接 pytest 目标。"""
    if not requirements.backend_required:
        return
    _run(["uv", "run", "ruff", "format", "--check", "backend", "tests", "scripts"])
    _run(["uv", "run", "ruff", "check", "backend", "tests", "scripts"])
    _run(["uv", "run", "mypy", "backend/src"])
    targets = tuple(requirements.backend_targets)
    if targets == ("all",):
        _run(["uv", "run", "pytest", "tests/unit", "tests/contracts", "tests/api", "-q"])
    elif targets:
        _run(["uv", "run", "pytest", *targets, "-q"])
    _run(["uv", "run", "python", "scripts/quality/check_architecture.py"])
    _run(["uv", "run", "python", "scripts/quality/check_table_ownership.py"])


def _run_contract(requirements: Any) -> None:
    """执行公共 Contract 与 generated client 漂移检查。"""
    if not requirements.contract_required:
        return
    _run(["uv", "run", "python", "scripts/contracts/generate.py"])
    _run(["npm", "--prefix", "frontend", "run", "generate:api"])
    _run(["git", "diff", "--exit-code", "--", "contracts", "frontend/src/generated/api"])
    _run(["uv", "run", "python", "scripts/contracts/generate.py", "--check"])
    _run(["uv", "run", "python", "scripts/contracts/check_compatibility.py"])


def _run_frontend(requirements: Any) -> None:
    """执行 Frontend lint/build 与 classifier 选择的 Unit/Browser 目标。"""
    if not requirements.frontend_required:
        return
    _run(["npm", "--prefix", "frontend", "run", "lint"])
    unit_targets = tuple(requirements.frontend_unit_targets)
    if unit_targets == ("all",):
        _run(["npm", "--prefix", "frontend", "run", "test", "--", "--run"])
    elif unit_targets:
        _run(["npm", "--prefix", "frontend", "run", "test", "--", "--run", *unit_targets])
    _run(["npm", "--prefix", "frontend", "run", "build"])
    browser_targets = tuple(requirements.frontend_browser_targets)
    if browser_targets == ("all",):
        _run(["npm", "--prefix", "frontend", "run", "test:e2e"])
    elif browser_targets:
        _run(["npm", "--prefix", "frontend", "run", "test:e2e", "--", *browser_targets])


def _run_repository_checks(requirements: Any) -> None:
    """执行所有 changed-scope 都可安全复用的仓库治理检查。"""
    _run(["python", "scripts/quality/scan_secrets.py"])
    _run(["python", "scripts/quality/check_docs.py"])
    _run(["python", "scripts/quality/check_docs_facts.py"])
    if requirements.repository_quality_required and not requirements.backend_required:
        _run(["uv", "run", "pytest", "tests/unit/test_agent_governance.py", "-q"])


def _print_deferred(requirements: Any) -> None:
    """明确列出需要真实基础设施、留给正式 CI 的独立 Evidence。"""
    if requirements.postgres_required:
        print(
            "PostgreSQL: required in Final CI; local preflight does not start or mutate a database automatically."
        )
    if requirements.fullstack_required:
        print(
            "Full-stack: required in Final CI; local preflight does not start the real browser/API/DB stack automatically."
        )


def main() -> int:
    """解析当前 diff，默认输出 plan；显式 --run 时执行安全本地层。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="main", help="Git 基线 revision，默认 main")
    parser.add_argument("--head", default="HEAD", help="Git 目标 revision，默认 HEAD")
    parser.add_argument(
        "--run",
        action="store_true",
        help="执行安全本地层；PostgreSQL/Real Full-stack 仍由 Final CI 负责",
    )
    args = parser.parse_args()

    base = _resolve_revision(args.base)
    head = _resolve_revision(args.head)
    changed_paths = _changed_paths(base, head)
    if changed_paths is None:
        raise SystemExit("无法可靠读取 changed paths；拒绝用另一套猜测逻辑继续。")
    requirements = classify_requirements(changed_paths)

    print(f"base={base}")
    print(f"head={head}")
    print(f"profile={requirements.profile}; changed_count={len(changed_paths)}")
    for path in changed_paths:
        print(f"- {path}")
    _print_targets("Backend targets", requirements.backend_targets)
    _print_targets("Frontend unit targets", requirements.frontend_unit_targets)
    _print_targets("Frontend browser targets", requirements.frontend_browser_targets)
    _print_targets("PostgreSQL targets", requirements.postgres_targets)
    _print_targets("PostgreSQL suites", requirements.postgres_suites)
    _print_targets("Full-stack specs", requirements.fullstack_specs)
    _print_deferred(requirements)

    if not args.run:
        return 0

    _run_repository_checks(requirements)
    _run_backend(requirements)
    _run_contract(requirements)
    _run_frontend(requirements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
