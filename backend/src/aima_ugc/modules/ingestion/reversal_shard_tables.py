"""两种撤回共享的 Content 范围工作单元；业务贡献仍由各自账本持有。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)

from aima_ugc.platform.database.metadata import metadata

reversal_shards_table = Table(
    "ingestion_reversal_shards",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("kind", Text(), nullable=False),
    Column(
        "import_campaign_id",
        Uuid(),
        ForeignKey("historical_import_revocation_requests.campaign_id"),
    ),
    Column("replay_request_id", Uuid(), ForeignKey("canonical_replay_all_requests.id")),
    Column("ordinal", Integer(), nullable=False),
    Column("lower_content_id", Uuid(), nullable=False),
    Column("upper_content_id", Uuid()),
    Column("job_id", Uuid(), ForeignKey("jobs.id")),
    Column("status", Text(), nullable=False),
    Column("checkpoint_content_id", Uuid()),
    Column("processed_content_count", Integer(), nullable=False, server_default="0"),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint(
        "(kind = 'import' and import_campaign_id is not null and replay_request_id is null) "
        "or (kind = 'replay' and import_campaign_id is null and replay_request_id is not null)",
        name="kind_parent_consistent",
    ),
    CheckConstraint(
        "status in ('pending','queued','running','succeeded','failed')", name="status_allowed"
    ),
    CheckConstraint("ordinal >= 0 and processed_content_count >= 0", name="counts_nonnegative"),
    CheckConstraint(
        "upper_content_id is null or lower_content_id < upper_content_id",
        name="range_ordered",
    ),
    CheckConstraint(
        "checkpoint_content_id is null or checkpoint_content_id >= lower_content_id",
        name="checkpoint_in_range",
    ),
    UniqueConstraint("import_campaign_id", "ordinal", name="uq_reversal_shard_import_ordinal"),
    UniqueConstraint("replay_request_id", "ordinal", name="uq_reversal_shard_replay_ordinal"),
    info={"owner": "ingestion"},
)

Index(
    "ix_reversal_shards_import_status",
    reversal_shards_table.c.import_campaign_id,
    reversal_shards_table.c.status,
)
Index(
    "ix_reversal_shards_replay_status",
    reversal_shards_table.c.replay_request_id,
    reversal_shards_table.c.status,
)

__all__ = ["reversal_shards_table"]
