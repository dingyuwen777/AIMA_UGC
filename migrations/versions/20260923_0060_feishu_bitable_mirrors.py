"""增加报告独立 Base 与文档内嵌 Base 的双向镜像状态。

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
