"""按稳定标签键顺序重编译已有 Analysis Scheme 快照。

Revision ID: 20260902_0038
Revises: 20260902_0037
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_0038"
down_revision: str | Sequence[str] | None = "20260902_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TAXONOMY_PLACEHOLDER = "{{AIMA_TAXONOMY_JSON}}"
_TAXONOMY_START = "<!-- AIMA_TAXONOMY_START -->"
_TAXONOMY_END = "<!-- AIMA_TAXONOMY_END -->"


def _compile_snapshot(
    definition: dict[str, Any], *, stable_label_order: bool
) -> tuple[str, str, str]:
    """使用本次迁移冻结的算法生成可重复的 Prompt 与 Hash。"""

    labels = definition["labels"]
    label_keys = sorted(labels) if stable_label_order else labels
    taxonomy_payload = {
        "schema_version": "aima-content-taxonomy.v2",
        "sentiments": list(definition["sentiments"]),
        "voice_types": list(definition["voice_types"]),
        "labels": {key: list(labels[key]) for key in label_keys},
    }
    readable_json = json.dumps(taxonomy_payload, ensure_ascii=False, indent=2)
    normalized_json = json.dumps(
        taxonomy_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    block = f"{_TAXONOMY_START}\n```json\n{readable_json}\n```\n{_TAXONOMY_END}"
    prompt_text = definition["prompt_template"].replace(_TAXONOMY_PLACEHOLDER, block)
    return (
        prompt_text,
        hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        hashlib.sha256(normalized_json).hexdigest(),
    )


def _rewrite_snapshots(*, stable_label_order: bool) -> None:
    """使用指定标签顺序策略重写全部持久化编译快照。"""

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, definition FROM analysis_scheme_versions")
    ).mappings()
    for row in rows:
        prompt_text, prompt_sha256, taxonomy_sha256 = _compile_snapshot(
            row["definition"], stable_label_order=stable_label_order
        )
        connection.execute(
            sa.text(
                "UPDATE analysis_scheme_versions "
                "SET compiled_prompt = :compiled_prompt, "
                "prompt_sha256 = :prompt_sha256, taxonomy_sha256 = :taxonomy_sha256 "
                "WHERE id = :id"
            ),
            {
                "id": row["id"],
                "compiled_prompt": prompt_text,
                "prompt_sha256": prompt_sha256,
                "taxonomy_sha256": taxonomy_sha256,
            },
        )


def upgrade() -> None:
    """修复所有已有版本，使数据库恢复校验与当前编译算法一致。"""

    _rewrite_snapshots(stable_label_order=True)


def downgrade() -> None:
    """按数据库当前键顺序重编译，使旧版运行时仍能恢复快照。"""

    _rewrite_snapshots(stable_label_order=False)
