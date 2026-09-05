from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARCHIVER_PATH = ROOT / "scripts" / "quality" / "archive_change_after_merge.py"


def _load_archiver() -> dict[str, Any]:
    """加载真实归档 helper，直接验证生命周期冻结边界。"""
    return runpy.run_path(str(ARCHIVER_PATH))


def _change(*, updated: str = "2026-09-05") -> str:
    """构造最小合法 Change，便于精确比较冻结前后文本。"""
    return f"""---
schema: coding-change/v1
id: CHG-20260905-same-day-fixture
title: Same-day archive fixture
level: L2
status: ready_for_review
owner: test
branch: test/same-day
created: 2026-09-05
updated: {updated}
completion_gate: required
depends_on: []
affected_areas: []
affected_paths: []
contracts: []
data_changes: []
---

# 正文

正文必须保持不变。
"""


def test_freeze_lifecycle_allows_same_day_updated_without_text_diff() -> None:
    """merge date 已等于 updated 时，只改变 status 也必须是合法冻结。"""
    module = _load_archiver()
    original = _change(updated="2026-09-05")

    frozen = module["freeze_lifecycle"](original, merged_date="2026-09-05")

    assert frozen == original.replace("status: ready_for_review", "status: done")
    assert "updated: 2026-09-05" in frozen


def test_freeze_lifecycle_cross_day_updates_status_and_date() -> None:
    """merge date 与 updated 不同时，两个生命周期字段仍必须正确冻结。"""
    module = _load_archiver()
    original = _change(updated="2026-09-04")

    frozen = module["freeze_lifecycle"](original, merged_date="2026-09-05")

    expected = original.replace("status: ready_for_review", "status: done").replace(
        "updated: 2026-09-04", "updated: 2026-09-05"
    )
    assert frozen == expected


def test_lifecycle_verifier_still_rejects_body_or_other_frontmatter_changes() -> None:
    """放宽 same-day diff 不能允许正文或其他 frontmatter 被归档流程改写。"""
    module = _load_archiver()
    error = module["ArchiveChangeError"]
    original = _change(updated="2026-09-05")
    legitimate = original.replace("status: ready_for_review", "status: done")

    with pytest.raises(error, match="frontmatter 之外"):
        module["_verify_lifecycle_only"](
            original,
            legitimate.replace("正文必须保持不变。", "正文被篡改。"),
            merged_date="2026-09-05",
        )

    with pytest.raises(error, match="未授权字段"):
        module["_verify_lifecycle_only"](
            original,
            legitimate.replace(
                "title: Same-day archive fixture",
                "title: Unexpected archive mutation",
            ),
            merged_date="2026-09-05",
        )
