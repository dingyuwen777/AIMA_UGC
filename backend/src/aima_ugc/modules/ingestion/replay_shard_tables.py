"""一个 Replay Run 内按稳定内容身份分片的持久断点与结果。"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)

from aima_ugc.platform.database.metadata import metadata

canonical_replay_run_shards_table = Table(
    "canonical_replay_run_shards",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column(
        "run_id", Uuid(), ForeignKey("canonical_replay_runs.id", ondelete="CASCADE"), nullable=False
    ),
    Column("ordinal", Integer(), nullable=False),
    Column("shard_count", Integer(), nullable=False),
    Column("job_id", Uuid(), ForeignKey("jobs.id")),
    Column("status", Text(), nullable=False),
    Column("checkpoint_artifact_ordinal", Integer(), nullable=False, server_default="0"),
    Column("checkpoint_row_number", BigInteger(), nullable=False, server_default="0"),
    Column("rows_seen", BigInteger(), nullable=False, server_default="0"),
    Column("rows_matched", BigInteger(), nullable=False, server_default="0"),
    Column("rows_filtered_out", BigInteger(), nullable=False, server_default="0"),
    Column("duplicates_removed", BigInteger(), nullable=False, server_default="0"),
    Column("rows_ingested", BigInteger(), nullable=False, server_default="0"),
    Column("existing_convergence", BigInteger(), nullable=False, server_default="0"),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint(
        "ordinal >= 0 and shard_count >= 1 and ordinal < shard_count", name="ordinal_range"
    ),
    CheckConstraint(
        "status in ('pending','queued','running','succeeded','failed')", name="status_allowed"
    ),
    CheckConstraint(
        "checkpoint_artifact_ordinal >= 0 and checkpoint_row_number >= 0",
        name="checkpoint_nonnegative",
    ),
    CheckConstraint(
        "rows_seen >= 0 and rows_matched >= 0 and rows_filtered_out >= 0 "
        "and duplicates_removed >= 0 and rows_ingested >= 0 and existing_convergence >= 0 "
        "and rows_seen = rows_matched + rows_filtered_out "
        "and rows_matched = duplicates_removed + rows_ingested + existing_convergence",
        name="counters_reconciled",
    ),
    UniqueConstraint("run_id", "ordinal", name="uq_canonical_replay_run_shards_ordinal"),
    info={"owner": "ingestion"},
)

__all__ = ["canonical_replay_run_shards_table"]
