"""让 Analysis voice_type 由 Prompt Taxonomy 管理合法值。

Revision ID: 20260828_0030
Revises: 20260827_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0030"
down_revision: str | Sequence[str] | None = "20260827_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_VOICE_TYPE_CHECK = (
    "voice_type in ('user_voice','creator_marketing','brand_official','dealer_promotion',"
    "'media_information','other_organization','unknown')"
)


def upgrade() -> None:
    """移除业务值枚举，只保留数据库层非空结构约束。"""

    op.drop_constraint(
        op.f("ck_analysis_content_results_voice_type_allowed"),
        "analysis_content_results",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_results_voice_type_nonempty"),
        "analysis_content_results",
        "char_length(voice_type) > 0",
    )


def downgrade() -> None:
    """仅在现有数据仍兼容旧七值 Schema 时恢复历史约束。"""

    connection = op.get_bind()
    unsupported = tuple(
        connection.execute(
            sa.text(
                "SELECT DISTINCT voice_type FROM analysis_content_results "
                "WHERE NOT (" + _LEGACY_VOICE_TYPE_CHECK + ") ORDER BY voice_type"
            )
        ).scalars()
    )
    if unsupported:
        values = ", ".join(unsupported)
        raise RuntimeError(
            "无法降级 voice_type Taxonomy：数据库已包含旧七值约束不支持的值: " + values
        )

    op.drop_constraint(
        op.f("ck_analysis_content_results_voice_type_nonempty"),
        "analysis_content_results",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_results_voice_type_allowed"),
        "analysis_content_results",
        _LEGACY_VOICE_TYPE_CHECK,
    )
