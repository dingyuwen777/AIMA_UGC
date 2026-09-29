from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "dev" / "validate_changed.py"


def test_validate_changed_reuses_canonical_ci_classifier() -> None:
    """开发期入口必须直接复用 CI classifier，而不是维护第二套 impact mapping。"""
    assert SCRIPT.is_file()
    namespace = runpy.run_path(str(SCRIPT))
    assert namespace["CLASSIFIER_PATH"] == ROOT / "scripts" / "quality" / "classify_ci_scope.py"


def test_validate_changed_exposes_plan_and_explicit_execution_mode() -> None:
    """默认只输出 plan；执行验证必须显式选择 run。"""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--run" in text
    assert "classify_requirements" in text
    assert "backend_targets" in text
    assert "frontend_unit_targets" in text
    assert "frontend_browser_targets" in text
    assert "PostgreSQL" in text
    assert "Full-stack" in text


def test_project_development_rules_bind_preflight_commit_hygiene_and_final_sync() -> None:
    """AIMA Overlay 只绑定项目入口与交付节奏，不复制第二套通用治理。"""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    blueprint = (ROOT / "docs" / "blueprint" / "06_开发约束与分阶段实施.md").read_text(
        encoding="utf-8"
    )
    for marker in (
        "scripts/dev/validate_changed.py",
        "临时 Workflow",
        "Draft 阶段",
        "Final 前",
        "bypass",
    ):
        assert marker in agents
        assert marker in blueprint
