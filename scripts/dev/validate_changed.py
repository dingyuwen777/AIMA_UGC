"""基于 CI classifier 生成并执行开发期 changed-scope preflight。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / "scripts" / "quality" / "classify_ci_scope.py"


def _git_ref_exists(ref: str) -> bool:
    """判断本地 checkout 是否存在指定 Git revision。"""
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def default_base() -> str:
    """优先使用本地 origin/main；没有 remote ref 时回退 main。"""
    for candidate in ("origin/main", "main"):
        if _git_ref_exists(candidate):
            return candidate
    raise SystemExit("无法解析 origin/main 或 main；请使用 --base 显式指定基线。")


def classify(base: str, head: str) -> dict[str, Any]:
    """调用唯一 CI classifier，禁止在开发入口复制 impact mapping。"""
    completed = subprocess.run(
        [
            sys.executable,
            str(CLASSIFIER),
            "--base",
            base,
            "--head",
            head,
            "--json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _all_or_targets(
    selected: list[str],
    *,
    all_command: tuple[str, ...],
    targeted_prefix: tuple[str, ...],
) -> list[tuple[str, ...]]:
    """把 all sentinel 或精确目标转成可执行命令。"""
    if not selected:
        return []
    if "all" in selected:
        return [all_command]
    return [(*targeted_prefix, *selected, "-q")]


def _frontend_relative(paths: list[str]) -> tuple[str, ...]:
    """把 classifier 的仓库相对路径转换为 frontend package 相对路径。"""
    return tuple(path.removeprefix("frontend/") for path in paths)


def build_fix_commands(requirements: dict[str, Any]) -> list[tuple[str, ...]]:
    """生成提交前可安全收敛的 formatter/generated 命令，不复制风险分类。"""
    commands: list[tuple[str, ...]] = []
    changed_python = tuple(
        path
        for path in requirements.get("changed_paths", [])
        if path.endswith(".py")
        and path.startswith(("backend/", "tests/", "scripts/", "migrations/"))
    )
    if changed_python:
        commands.append(("uv", "run", "ruff", "format", *changed_python))
    if requirements.get("contract_required"):
        commands.extend(
            [
                ("uv", "run", "python", "scripts/contracts/generate.py"),
                ("npm", "--prefix", "frontend", "run", "generate:api"),
            ]
        )
    return commands


def build_validation_commands(requirements: dict[str, Any]) -> list[tuple[str, ...]]:
    """根据 classifier 输出构造无外部服务副作用的本地验证命令。"""
    commands: list[tuple[str, ...]] = []

    if requirements.get("backend_required"):
        changed_python = tuple(
            path
            for path in requirements.get("changed_paths", [])
            if path.endswith(".py")
            and path.startswith(("backend/", "tests/", "scripts/", "migrations/"))
        )
        if changed_python:
            commands.append(("uv", "run", "ruff", "format", "--check", *changed_python))
            commands.append(("uv", "run", "ruff", "check", *changed_python))
        commands.append(("uv", "run", "mypy", "backend/src"))
        commands.extend(
            _all_or_targets(
                list(requirements.get("backend_targets", [])),
                all_command=(
                    "uv",
                    "run",
                    "pytest",
                    "tests/unit",
                    "tests/contracts",
                    "tests/api",
                    "-q",
                ),
                targeted_prefix=("uv", "run", "pytest"),
            )
        )

    if requirements.get("contract_required"):
        commands.extend(
            [
                ("uv", "run", "python", "scripts/contracts/generate.py", "--check"),
                ("uv", "run", "python", "scripts/contracts/check_compatibility.py"),
            ]
        )

    if requirements.get("frontend_required"):
        commands.append(("npm", "--prefix", "frontend", "run", "lint"))
        unit_targets = list(requirements.get("frontend_unit_targets", []))
        if "all" in unit_targets:
            commands.append(("npm", "--prefix", "frontend", "run", "test", "--", "--run"))
        elif unit_targets:
            commands.append(
                (
                    "npm",
                    "--prefix",
                    "frontend",
                    "exec",
                    "--",
                    "vitest",
                    "run",
                    *_frontend_relative(unit_targets),
                )
            )
        commands.append(("npm", "--prefix", "frontend", "run", "build"))
        e2e_specs = list(requirements.get("frontend_e2e_specs", []))
        if "all" in e2e_specs:
            commands.append(("npm", "--prefix", "frontend", "run", "test:e2e"))
        elif e2e_specs:
            commands.append(
                (
                    "npm",
                    "--prefix",
                    "frontend",
                    "exec",
                    "--",
                    "playwright",
                    "test",
                    *_frontend_relative(e2e_specs),
                )
            )
    return commands


def deferred_ci_layers(requirements: dict[str, Any]) -> tuple[str, ...]:
    """列出默认不在本地伪造、继续由正式 CI 证明的真实重依赖层。"""
    deferred: list[str] = []
    if requirements.get("repository_quality_required") and not requirements.get("backend_required"):
        deferred.append("Repository Quality")
    if requirements.get("repository_quality_required") and not requirements.get("backend_required"):
        deferred.append("Repository Quality")
    if requirements.get("postgres_required"):
        deferred.append("PostgreSQL Integration")
    if requirements.get("fullstack_required"):
        deferred.append("Real Full-stack Golden Path")
    return tuple(deferred)


def _print_plan(requirements: dict[str, Any], commands: list[tuple[str, ...]]) -> None:
    """输出人类可读的 changed-scope 计划。"""
    print(
        "Preflight profile="
        f"{requirements.get('profile')}; changed_count={requirements.get('changed_count', 0)}"
    )
    for path in requirements.get("changed_paths", []):
        print(f"- {path}")
    fix_commands = build_fix_commands(requirements)
    if fix_commands:
        print("Optional fix before validation:")
        for command in fix_commands:
            print("  " + " ".join(command))
    print("Local validation:")
    for command in commands:
        print("  " + " ".join(command))
    deferred = deferred_ci_layers(requirements)
    if deferred:
        print("Deferred to formal CI:")
        for layer in deferred:
            print(f"  - {layer}")


def _execute(commands: list[tuple[str, ...]]) -> None:
    """顺序执行无外部服务副作用的本地验证并保留原始退出码。"""
    for command in commands:
        print("+ " + " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    """解析基线，输出计划，并按需执行本地 preflight。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Git 基线；默认 origin/main，其次 main")
    parser.add_argument("--head", default="HEAD", help="Git 目标 revision，默认 HEAD")
    parser.add_argument("--fix", action="store_true", help="先收敛 changed Python 格式和 generated artifacts")
    parser.add_argument("--execute", action="store_true", help="执行本地稳定验证层")
    parser.add_argument("--json", action="store_true", help="输出 classifier JSON")
    args = parser.parse_args()

    base = args.base or default_base()
    requirements = classify(base, args.head)
    commands = build_validation_commands(requirements)
    if args.json:
        print(json.dumps(requirements, ensure_ascii=False, sort_keys=True))
    else:
        _print_plan(requirements, commands)
    if args.fix:
        _execute(build_fix_commands(requirements))
    if args.execute:
        _execute(commands)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
