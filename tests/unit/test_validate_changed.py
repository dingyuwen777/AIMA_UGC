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
    assert any("vitest" in command and "frontend/tests/voice-plaza.spec.ts" in command for command in rendered)
    assert any("playwright test" in command and "frontend/e2e/voice-plaza.spec.ts" in command for command in rendered)


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
