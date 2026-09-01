from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPLETION_GATE = ROOT / ".github/workflows/change-completion-gate.yml"


def test_requirement_source_gate_revalidates_pr_body_edits() -> None:
    """PR 正文改变 Requirement Source 时必须重新执行同一个 Required Check。"""
    workflow = COMPLETION_GATE.read_text(encoding="utf-8")

    assert "types:" in workflow
    assert "- edited" in workflow
