from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESOLVER = runpy.run_path(str(ROOT / "scripts" / "quality" / "resolve_main_evidence.py"))
EVALUATE_REUSE = RESOLVER["evaluate_reuse"]


def _check(name: str, *, conclusion: str = "success", completed_at: str = "2026-09-28T00:00:00Z") -> dict[str, object]:
    """构造最小 GitHub check fixture，覆盖最终成功与失败状态。"""
    return {
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": completed_at,
        "started_at": completed_at,
    }


def test_same_tree_and_latest_required_check_success_can_reuse() -> None:
    result = EVALUATE_REUSE(
        current_tree="tree-a",
        source_tree="tree-a",
        required_checks=("CI Gate",),
        check_runs=(
            _check("CI Gate", conclusion="failure", completed_at="2026-09-27T23:00:00Z"),
            _check("CI Gate", conclusion="success", completed_at="2026-09-28T00:00:00Z"),
        ),
    )

    assert result.reusable is True
    assert result.reason == "reusable"


def test_tree_mismatch_fails_closed() -> None:
    result = EVALUATE_REUSE(
        current_tree="tree-main",
        source_tree="tree-pr",
        required_checks=("CI Gate",),
        check_runs=(_check("CI Gate"),),
    )

    assert result.reusable is False
    assert result.reason == "tree_mismatch"


def test_missing_or_failed_required_check_fails_closed() -> None:
    missing = EVALUATE_REUSE(
        current_tree="same",
        source_tree="same",
        required_checks=("CI Gate", "Compose Golden Path"),
        check_runs=(_check("CI Gate"),),
    )
    failed = EVALUATE_REUSE(
        current_tree="same",
        source_tree="same",
        required_checks=("CI Gate",),
        check_runs=(_check("CI Gate", conclusion="failure"),),
    )

    assert missing.reusable is False
    assert missing.reason == "required_check_not_green"
    assert failed.reusable is False
    assert failed.reason == "required_check_not_green"
