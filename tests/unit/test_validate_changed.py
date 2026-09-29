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
