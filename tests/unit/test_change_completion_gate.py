from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPLETION_OWNER = ROOT / ".github/workflows/ci.yml"


def test_requirement_source_gate_revalidates_pr_body_edits_without_product_ci() -> None:
    """PR 正文改变 Requirement Source 时必须重跑 traceability，但不应重跑产品层。"""
    workflow = COMPLETION_OWNER.read_text(encoding="utf-8")
    assert "types:" in workflow
    assert "- edited" in workflow
    assert "profile=metadata_only" in workflow
    assert "repository_required=false" in workflow
    assert "postgres_required=false" in workflow
    assert "fullstack_required=false" in workflow
