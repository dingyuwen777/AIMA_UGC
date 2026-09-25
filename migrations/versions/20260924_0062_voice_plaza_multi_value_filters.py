"""声音广场筛选支持情感、发声类型多值，并回填历史快照。

Revision ID: 20260924_0062
Revises: 20260924_0061
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0062"
down_revision: str | Sequence[str] | None = "20260924_0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SINGLE_TO_MULTI = {
    "voice_type": "voice_types",
    "sentiment": "sentiments",
}
_MULTI_TO_SINGLE = {value: key for key, value in _SINGLE_TO_MULTI.items()}


def _migrate_single_to_multi(filters: dict[str, Any]) -> dict[str, Any] | None:
    """把单值 voice_type / sentiment 转成单元素数组；无变化返回 None。"""

    changed = False
    for single, multi in _SINGLE_TO_MULTI.items():
        if isinstance(filters.get(single), str):
            filters[multi] = [filters.pop(single)]
            changed = True
    return filters if changed else None


def _migrate_multi_to_single(filters: dict[str, Any]) -> dict[str, Any] | None:
    """把数组回退为单值；多值无法无损还原时拒绝。"""

    changed = False
    for multi, single in _MULTI_TO_SINGLE.items():
        value = filters.get(multi)
        if not isinstance(value, list):
            continue
        if len(value) > 1:
            raise RuntimeError(
                "无法降级：历史快照已包含多值 voice_types / sentiments，单值字段无法无损还原"
            )
        del filters[multi]
        if value:
            filters[single] = value[0]
        changed = True
    return filters if changed else None


def _update_jsonb(bind: Any, table: str, column: str, row_id: Any, value: dict[str, Any]) -> None:
    bind.execute(
        sa.text(f"UPDATE {table} SET {column} = :snapshot::jsonb WHERE id = :id"),
        {"snapshot": json.dumps(value, ensure_ascii=False), "id": row_id},
    )


def upgrade() -> None:
    bind = op.get_bind()

    for row in bind.execute(
        sa.text("SELECT id, filter_snapshot FROM analysis_content_runs")
    ).mappings():
        snapshot = dict(row["filter_snapshot"] or {})
        normalized = _migrate_single_to_multi(snapshot)
        if normalized is not None:
            _update_jsonb(bind, "analysis_content_runs", "filter_snapshot", row["id"], normalized)

    for row in bind.execute(
        sa.text("SELECT id, request_snapshot FROM reporting_data_exports")
    ).mappings():
        snapshot = dict(row["request_snapshot"] or {})
        filters = snapshot.get("filters")
        if isinstance(filters, dict):
            normalized = _migrate_single_to_multi(dict(filters))
            if normalized is not None:
                snapshot["filters"] = normalized
                _update_jsonb(
                    bind,
                    "reporting_data_exports",
                    "request_snapshot",
                    row["id"],
                    snapshot,
                )


def downgrade() -> None:
    bind = op.get_bind()

    for row in bind.execute(
        sa.text("SELECT id, filter_snapshot FROM analysis_content_runs")
    ).mappings():
        snapshot = dict(row["filter_snapshot"] or {})
        normalized = _migrate_multi_to_single(snapshot)
        if normalized is not None:
            _update_jsonb(bind, "analysis_content_runs", "filter_snapshot", row["id"], normalized)

    for row in bind.execute(
        sa.text("SELECT id, request_snapshot FROM reporting_data_exports")
    ).mappings():
        snapshot = dict(row["request_snapshot"] or {})
        filters = snapshot.get("filters")
        if isinstance(filters, dict):
            normalized = _migrate_multi_to_single(dict(filters))
            if normalized is not None:
                snapshot["filters"] = normalized
                _update_jsonb(
                    bind,
                    "reporting_data_exports",
                    "request_snapshot",
                    row["id"],
                    snapshot,
                )
