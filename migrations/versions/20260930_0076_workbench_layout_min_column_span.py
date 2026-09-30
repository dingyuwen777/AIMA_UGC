"""工作台布局最小列宽统一提升到 5，并回填历史布局。

Revision ID: 20260930_0076
Revises: 20260929_0075
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0076"
down_revision: str | Sequence[str] | None = "20260929_0075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MIN_COLUMN_SPAN = 5


def _normalize(layout: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """把 column_span 小于 5 的模块统一抬到 5；无变化返回 None。"""

    changed = False
    for item in layout:
        span = item.get("column_span")
        if isinstance(span, int) and span < _MIN_COLUMN_SPAN:
            item["column_span"] = _MIN_COLUMN_SPAN
            changed = True
    return layout if changed else None


def _update_layout(bind: Any, principal_id: str, layout: list[dict[str, Any]]) -> None:
    bind.execute(
        sa.text(
            "UPDATE workbench_layouts SET layout = CAST(:layout AS jsonb) "
            "WHERE principal_id = :principal_id"
        ),
        {
            "layout": json.dumps(layout, ensure_ascii=False),
            "principal_id": principal_id,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    for row in bind.execute(
        sa.text("SELECT principal_id, layout FROM workbench_layouts")
    ).mappings():
        layout = [dict(item) for item in (row["layout"] or [])]
        normalized = _normalize(layout)
        if normalized is not None:
            _update_layout(bind, row["principal_id"], normalized)


def downgrade() -> None:
    """最小列宽从 5 回退到 4 无需改动数据：5 仍然是合法值。"""
