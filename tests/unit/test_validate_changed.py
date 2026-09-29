from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "dev" / "validate_changed.py"


def test_validate_changed_reuses_classifier_and_builds_targeted_commands() -> None:
    """开发期入口只消费 classifier 输出，不维护第二套 changed-scope 映射。"""
    script = runpy.run_path(str(SCRIPT_PATH))
    build_commands = script["build_validation_commands"]

    commands = build_commands(
        {
            "profile": "cross_component",
            "repository_quality_required": False,
            "backend_required": True,
            "changed_paths": ["backend/src/aima_ugc/modules/analysis/content_analysis_job.py"],
            "backend_targets": ["tests/unit/analysis"],
            "frontend_required": True,
            "frontend_unit_targets": ["frontend/tests/voice-plaza.spec.ts"],
            "frontend_e2e_specs": ["frontend/e2e/voice-plaza.spec.ts"],
            "contract_required": False,
            "postgres_required": False,
            "fullstack_required": False,
        }
    )

    rendered = [" ".join(command) for command in commands]
    assert any("pytest tests/unit/analysis -q" in command for command in rendered)
    assert any("vitest" in command and "tests/voice-plaza.spec.ts" in command for command in rendered)
    assert any("playwright test" in command and "e2e/voice-plaza.spec.ts" in command for command in rendered)


def test_validate_changed_keeps_expensive_external_layers_as_explicit_ci_deferred_items() -> None:
    """开发入口不伪造本地 PostgreSQL/Full-stack 环境，必须显式标记由正式 CI 证明。"""
    script = runpy.run_path(str(SCRIPT_PATH))
    deferred = script["deferred_ci_layers"](
        {
            "postgres_required": True,
            "fullstack_required": True,
        }
    )

    assert deferred == ("PostgreSQL Integration", "Real Full-stack Golden Path")


def test_validate_changed_fix_only_formats_changed_python_and_regenerates_contracts() -> None:
    """--fix 只收敛 changed Python 与真实 generated owner，不格式化无关文件。"""
    script = runpy.run_path(str(SCRIPT_PATH))
    commands = script["build_fix_commands"](
        {
            "changed_paths": [
                "backend/src/aima_ugc/modules/analysis/content_analysis_job.py",
                "frontend/src/features/voice-plaza/store.ts",
            ],
            "contract_required": True,
        }
    )
    rendered = [" ".join(command) for command in commands]
    assert any(
        "ruff format backend/src/aima_ugc/modules/analysis/content_analysis_job.py" in command
        for command in rendered
    )
    assert any("scripts/contracts/generate.py" in command for command in rendered)
    assert any("frontend run generate:api" in command for command in rendered)
    assert all("frontend/src/features/voice-plaza/store.ts" not in command for command in rendered)


def test_validate_changed_defers_repository_quality_without_inventing_second_mapping() -> None:
    """仓库治理专项没有 classifier targets 时显式留给 CI，而不是硬编码另一套列表。"""
    script = runpy.run_path(str(SCRIPT_PATH))
    assert script["deferred_ci_layers"](
        {
            "repository_quality_required": True,
            "backend_required": False,
            "postgres_required": False,
            "fullstack_required": False,
        }
    ) == ("Repository Quality",)


def test_validate_changed_default_scope_includes_worktree_and_untracked(monkeypatch) -> None:
    """提交前预检默认覆盖 HEAD 后 staged/unstaged 与 untracked 文件。"""
    script = runpy.run_path(str(SCRIPT_PATH))
    calls: list[tuple[str, ...]] = []

    def fake_git_paths(command: list[str]) -> tuple[str, ...]:
        calls.append(tuple(command))
        if command[1:3] == ["diff", "--no-renames"]:
            return (
                "backend/src/aima_ugc/modules/analysis/content_analysis_job.py",
                "frontend/src/features/voice-plaza/store.ts",
            )
        return ("tests/unit/analysis/test_new_rule.py",)

    monkeypatch.setitem(script["_git_paths"].__globals__, "_git_paths", fake_git_paths)
    paths = script["changed_paths"]("origin/main", "HEAD", include_worktree=True)

    assert paths == (
        "backend/src/aima_ugc/modules/analysis/content_analysis_job.py",
        "frontend/src/features/voice-plaza/store.ts",
        "tests/unit/analysis/test_new_rule.py",
    )
    assert any(command[:3] == ("git", "diff", "--no-renames") for command in calls)
    assert any(command[:3] == ("git", "ls-files", "--others") for command in calls)


def test_validate_changed_committed_only_keeps_explicit_base_head_diff(monkeypatch) -> None:
    """显式 committed-only 不读取 working tree，便于复现已提交 revision Evidence。"""
    script = runpy.run_path(str(SCRIPT_PATH))
    calls: list[tuple[str, ...]] = []

    def fake_git_paths(command: list[str]) -> tuple[str, ...]:
        calls.append(tuple(command))
        return ("backend/src/aima_ugc/modules/content/service.py",)

    monkeypatch.setitem(script["_git_paths"].__globals__, "_git_paths", fake_git_paths)
    paths = script["changed_paths"]("main", "feature-head", include_worktree=False)

    assert paths == ("backend/src/aima_ugc/modules/content/service.py",)
    assert calls == [
        ("git", "diff", "--no-renames", "--name-only", "-z", "main", "feature-head")
    ]
