"""建立内容分析人工纠正锁定当前态。

Revision ID: 20260902_0036
Revises: 20260902_0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260902_0036"
down_revision: str | Sequence[str] | None = "20260902_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_content_manual_overrides",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("voice_type", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.Text(), nullable=True),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("voice_type_locked", sa.Boolean(), nullable=False),
        sa.Column("sentiment_locked", sa.Boolean(), nullable=False),
        sa.Column("labels_locked", sa.Boolean(), nullable=False),
        sa.Column("actor_ref", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_version > 0",
            name=op.f("ck_analysis_content_manual_overrides_content_version_positive"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(labels) = 'array'",
            name=op.f("ck_analysis_content_manual_overrides_labels_array"),
        ),
        sa.CheckConstraint(
            "(voice_type_locked and voice_type is not null) or "
            "(not voice_type_locked and voice_type is null)",
            name=op.f("ck_analysis_content_manual_overrides_voice_type_lock_consistent"),
        ),
        sa.CheckConstraint(
            "(sentiment_locked and sentiment is not null) or "
            "(not sentiment_locked and sentiment is null)",
            name=op.f("ck_analysis_content_manual_overrides_sentiment_lock_consistent"),
        ),
        sa.CheckConstraint(
            "labels_locked or labels = '[]'::jsonb",
            name=op.f("ck_analysis_content_manual_overrides_labels_lock_consistent"),
        ),
        sa.CheckConstraint(
            "char_length(actor_ref) > 0",
            name=op.f("ck_analysis_content_manual_overrides_actor_ref_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_analysis_content_manual_overrides_content_id_contents"),
        ),
        sa.PrimaryKeyConstraint(
            "content_id",
            "content_version",
            name=op.f("pk_analysis_content_manual_overrides"),
        ),
    )


def downgrade() -> None:
    op.drop_table("analysis_content_manual_overrides")
