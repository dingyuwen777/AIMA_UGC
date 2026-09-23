"""持久化 Canonical Replay 预检证明，供后续重筛安全复用。

Revision ID: 20260923_0060
Revises: 20260922_0059
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260923_0060"
down_revision: str | Sequence[str] | None = "20260922_0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """只新增内部证明表；历史 Artifact 首次重筛时按原路径验证回填。"""

    op.create_table(
        "canonical_replay_validation_proofs",
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("validation_version", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_expectations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(sha256) = 64",
            name=op.f("ck_canonical_replay_validation_proofs_sha256_length"),
        ),
        sa.CheckConstraint(
            "byte_size >= 0",
            name=op.f("ck_canonical_replay_validation_proofs_byte_size_nonnegative"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_expectations) = 'array'",
            name=op.f("ck_canonical_replay_validation_proofs_source_expectations_array"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_canonical_replay_validation_proofs_artifact_id_artifacts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("artifact_id", name=op.f("pk_canonical_replay_validation_proofs")),
    )


def downgrade() -> None:
    """移除可再生证明，不删除 Canonical 或业务内容。"""

    op.drop_table("canonical_replay_validation_proofs")
