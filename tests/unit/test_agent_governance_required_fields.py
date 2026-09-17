from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "scripts" / "quality" / "check_agent_governance.py"))
CHECK_ISSUE_FORM = CHECKER["_check_issue_form"]


def test_required_textarea_cannot_be_hidden_by_other_required_controls(tmp_path: Path) -> None:
    """其他 checkbox 的 required 计数不能掩盖必需 textarea 被弱化为 optional。"""
    form = tmp_path / "01-requirement.yml"
    form.write_text(
        """name: 需求
description: fixture
title: "[需求] "
body:
  - type: checkboxes
    id: duplicate_search
    attributes:
      label: 重复检查
    validations:
      required: true
  - type: textarea
    id: objective
    attributes:
      label: 目标
    validations:
      required: false
  - type: textarea
    id: scope
    attributes:
      label: 范围
    validations:
      required: true
""",
        encoding="utf-8",
    )

    errors = CHECK_ISSUE_FORM(form, ("id: objective", "id: scope"))

    assert any("GOV012" in error and "required" in error for error in errors)
