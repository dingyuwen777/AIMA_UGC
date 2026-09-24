"""增加报告独立 Base 与文档内嵌 Base 的双向镜像状态。

Revision ID: 20260923_0060_feishu
Revises: 20260923_0060
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260923_0060_feishu"
down_revision: str | Sequence[str] | None = "20260923_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ensure_canonical_replay_validation_proofs() -> None:
    """Repair databases that previously recorded the Feishu migration as 0060.

    A merge briefly shipped two different migrations with the same revision ID.
    Some local databases therefore report 0060 while already containing the
    Feishu table but not the canonical replay validation table.  The normal
    0060 migration has already been marked as applied in those databases, so
    this follow-up migration must restore the missing table before continuing.
    """

    bind = op.get_bind()
    if sa.inspect(bind).has_table("canonical_replay_validation_proofs"):
        return
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


def upgrade() -> None:
    _ensure_canonical_replay_validation_proofs()
    if sa.inspect(op.get_bind()).has_table("feishu_bitable_mirrors"):
        return
    op.create_table(
        "feishu_bitable_mirrors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_job_id", sa.Uuid(), nullable=True),
        sa.Column("document_token", sa.Text(), nullable=False),
        sa.Column("document_url", sa.Text(), nullable=False),
        sa.Column("external_app_token", sa.Text(), nullable=False),
        sa.Column("external_table_id", sa.Text(), nullable=False),
        sa.Column("embedded_app_token", sa.Text(), nullable=False),
        sa.Column("embedded_table_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column(
            "known_key_hashes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name=op.f("ck_feishu_bitable_mirrors_consecutive_failures_nonnegative"),
        ),
        sa.CheckConstraint(
            "status in ('active','paused')",
            name=op.f("ck_feishu_bitable_mirrors_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["publication_job_id"],
            ["jobs.id"],
            name=op.f("fk_feishu_bitable_mirrors_publication_job_id_jobs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feishu_bitable_mirrors")),
        sa.UniqueConstraint(
            "document_token",
            name=op.f("uq_feishu_bitable_mirrors_document_token"),
        ),
        sa.UniqueConstraint(
            "embedded_app_token",
            "embedded_table_id",
            name=op.f(
                "uq_feishu_bitable_mirrors_embedded_app_token_embedded_table_id"
            ),
        ),
        sa.UniqueConstraint(
            "external_app_token",
            "external_table_id",
            name=op.f(
                "uq_feishu_bitable_mirrors_external_app_token_external_table_id"
            ),
        ),
        sa.UniqueConstraint(
            "publication_job_id",
            name=op.f("uq_feishu_bitable_mirrors_publication_job_id"),
        ),
    )
    op.create_index(
        op.f("ix_feishu_bitable_mirrors_status_next_sync_at"),
        "feishu_bitable_mirrors",
        ["status", "next_sync_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_feishu_bitable_mirrors_status_next_sync_at"),
        table_name="feishu_bitable_mirrors",
    )
    op.drop_table("feishu_bitable_mirrors")
