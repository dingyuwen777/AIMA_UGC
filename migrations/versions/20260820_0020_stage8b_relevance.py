"""建立全局 Relevance 配置并增加 Candidate filtered 终态。

Revision ID: 20260820_0020
Revises: 20260820_0019
"""

import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0020"
down_revision: str | Sequence[str] | None = "20260820_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("uq_keywords_normalized_text"),
        "keywords",
        type_="unique",
    )
    _normalize_existing_keywords()
    op.create_unique_constraint(
        op.f("uq_keywords_normalized_text"),
        "keywords",
        ["normalized_text"],
    )
    op.create_table(
        "global_relevance_config",
        sa.Column("singleton_key", sa.Text(), nullable=False),
        sa.Column("keyword_pack_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "singleton_key = 'global'",
            name=op.f("ck_global_relevance_config_singleton_key_global"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_global_relevance_config_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["keyword_pack_id"],
            ["keyword_packs.id"],
            name=op.f("fk_global_relevance_config_keyword_pack_id_keyword_packs"),
        ),
        sa.PrimaryKeyConstraint(
            "singleton_key",
            name=op.f("pk_global_relevance_config"),
        ),
    )
    op.drop_constraint(
        op.f("ck_collection_candidate_ingestions_result_allowed"),
        "collection_candidate_ingestions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_collection_candidate_ingestions_result_allowed"),
        "collection_candidate_ingestions",
        "result in ('ingested','duplicate','filtered','invalid','unsupported','failed')",
    )


def downgrade() -> None:
    filtered_count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM collection_candidate_ingestions WHERE result = 'filtered'")
    )
    if int(filtered_count or 0) > 0:
        raise RuntimeError(
            "Stage 8B 已存在 filtered Candidate，不能安全 downgrade；"
            "请保留当前 Revision 或显式迁移这些账本事实"
        )
    op.drop_constraint(
        op.f("ck_collection_candidate_ingestions_result_allowed"),
        "collection_candidate_ingestions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_collection_candidate_ingestions_result_allowed"),
        "collection_candidate_ingestions",
        "result in ('ingested','duplicate','invalid','unsupported','failed')",
    )
    op.drop_table("global_relevance_config")


def _normalize_existing_keywords() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, text FROM keywords ORDER BY id")).mappings()
    normalized_by_id: list[tuple[object, str]] = []
    owners: dict[str, object] = {}
    for row in rows:
        normalized = unicodedata.normalize("NFKC", str(row["text"]).strip()).casefold()
        if not normalized:
            raise RuntimeError(f"关键词 {row['id']} 规范化后为空，Stage 8B Migration 已中止")
        owner = owners.get(normalized)
        if owner is not None and owner != row["id"]:
            raise RuntimeError(
                f"关键词 NFKC/casefold 身份冲突，Stage 8B Migration 已中止: {owner}, {row['id']}"
            )
        owners[normalized] = row["id"]
        normalized_by_id.append((row["id"], normalized))
    for keyword_id, normalized in normalized_by_id:
        connection.execute(
            sa.text("UPDATE keywords SET normalized_text = :normalized WHERE id = :id"),
            {"normalized": normalized, "id": keyword_id},
        )
