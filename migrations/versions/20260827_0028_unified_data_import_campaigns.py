"""把 Stage 12 Campaign 扩展为本地/服务器统一数据导入。

Revision ID: 20260827_0028
Revises: 20260826_0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0028"
down_revision: str | Sequence[str] | None = "20260826_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HISTORICAL_FIELDS_CONSTRAINT = "ck_processing_import_batches_historical_fields_consistent"
_LEGACY_DOUBLE_PREFIXED_HISTORICAL_FIELDS_CONSTRAINT = (
    "ck_processing_import_batches_ck_processing_import_batch_fa0e"
)


def _drop_historical_fields_constraint() -> None:
    """兼容 0026 开发期曾生成的二次前缀约束名。"""

    for constraint_name in (
        _HISTORICAL_FIELDS_CONSTRAINT,
        _LEGACY_DOUBLE_PREFIXED_HISTORICAL_FIELDS_CONSTRAINT,
    ):
        op.drop_constraint(
            op.f(constraint_name),
            "processing_import_batches",
            type_="check",
            if_exists=True,
        )


def upgrade() -> None:
    op.add_column(
        "historical_import_campaigns",
        sa.Column(
            "source_kind",
            sa.Text(),
            server_default=sa.text("'server_path'"),
            nullable=False,
        ),
    )
    op.add_column(
        "historical_import_campaigns",
        sa.Column(
            "ingestion_policy",
            sa.Text(),
            server_default=sa.text("'historical_fill_only'"),
            nullable=False,
        ),
    )
    op.add_column(
        "historical_import_campaigns",
        sa.Column("declared_file_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute("UPDATE historical_import_campaigns SET declared_file_count = discovered_file_count")
    op.drop_constraint(
        op.f("ck_historical_import_campaigns_status_allowed"),
        "historical_import_campaigns",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_historical_import_campaigns_status_allowed"),
        "historical_import_campaigns",
        "status in ('uploading','discovering','snapshotting','ready','queued','running',"
        "'cancelling','cancelled','succeeded','partial_failed','failed')",
    )
    op.create_check_constraint(
        op.f("ck_historical_import_campaigns_source_kind_allowed"),
        "historical_import_campaigns",
        "source_kind in ('local_upload','server_path')",
    )
    op.create_check_constraint(
        op.f("ck_historical_import_campaigns_ingestion_policy_allowed"),
        "historical_import_campaigns",
        "ingestion_policy in ('standard_observation','historical_fill_only')",
    )
    op.create_check_constraint(
        op.f("ck_historical_import_campaigns_declared_file_count_nonnegative"),
        "historical_import_campaigns",
        "declared_file_count >= 0",
    )

    _drop_historical_fields_constraint()
    op.create_check_constraint(
        op.f(_HISTORICAL_FIELDS_CONSTRAINT),
        "processing_import_batches",
        "(historical_campaign_item_id is null and historical_policy_version is null "
        "and retry_of_batch_id is null and not historical_mode) or "
        "(historical_campaign_item_id is not null "
        "and historical_policy_version in "
        "('historical-fill-only.v1','standard-observation.v1') "
        "and historical_mode = "
        "(historical_policy_version = 'historical-fill-only.v1'))",
    )

    op.drop_constraint(
        op.f("ck_processing_import_batch_items_outcome_allowed"),
        "processing_import_batch_items",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_processing_import_batch_items_outcome_allowed"),
        "processing_import_batch_items",
        "outcome in ('created','filled','updated','unchanged','conflict','filtered',"
        "'duplicate','invalid','failed')",
    )


def downgrade() -> None:
    connection = op.get_bind()
    unsupported = connection.scalar(
        sa.text(
            "SELECT count(*) FROM historical_import_campaigns "
            "WHERE source_kind <> 'server_path' "
            "OR ingestion_policy <> 'historical_fill_only' "
            "OR status = 'uploading'"
        )
    )
    updated_rows = connection.scalar(
        sa.text("SELECT count(*) FROM processing_import_batch_items WHERE outcome = 'updated'")
    )
    if unsupported or updated_rows:
        raise RuntimeError(
            "统一导入已产生本地、标准观测或 updated 账本；为避免丢失语义，禁止直接降级"
        )

    op.drop_constraint(
        op.f("ck_processing_import_batch_items_outcome_allowed"),
        "processing_import_batch_items",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_processing_import_batch_items_outcome_allowed"),
        "processing_import_batch_items",
        "outcome in ('created','filled','unchanged','conflict','filtered','duplicate',"
        "'invalid','failed')",
    )
    _drop_historical_fields_constraint()
    op.create_check_constraint(
        op.f(_HISTORICAL_FIELDS_CONSTRAINT),
        "processing_import_batches",
        "(historical_mode and historical_campaign_item_id is not null "
        "and historical_policy_version is not null) or "
        "(not historical_mode and historical_campaign_item_id is null "
        "and historical_policy_version is null and retry_of_batch_id is null)",
    )
    op.drop_constraint(
        op.f("ck_historical_import_campaigns_declared_file_count_nonnegative"),
        "historical_import_campaigns",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_historical_import_campaigns_ingestion_policy_allowed"),
        "historical_import_campaigns",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_historical_import_campaigns_source_kind_allowed"),
        "historical_import_campaigns",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_historical_import_campaigns_status_allowed"),
        "historical_import_campaigns",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_historical_import_campaigns_status_allowed"),
        "historical_import_campaigns",
        "status in ('discovering','snapshotting','ready','queued','running','cancelling',"
        "'cancelled','succeeded','partial_failed','failed')",
    )
    op.drop_column("historical_import_campaigns", "declared_file_count")
    op.drop_column("historical_import_campaigns", "ingestion_policy")
    op.drop_column("historical_import_campaigns", "source_kind")
