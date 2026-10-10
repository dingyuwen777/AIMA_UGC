"""Content Owner 的有限修复范围与持久检查点；不保存第二套内容事实。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.platform.database.metadata import metadata

content_consistency_repair_runs_table = Table(
    "content_consistency_repair_runs",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False, unique=True),
    Column("catalog_snapshot", JSONB(), nullable=False),
    Column("source_collection_run_id", Uuid(), ForeignKey("collection_runs.id")),
    Column("checkpoint_content_id", Uuid()),
    Column("batch_size", Integer(), nullable=False),
    Column("max_contents", Integer(), nullable=False),
    Column("target_count", Integer(), nullable=False),
    Column("processed_count", Integer(), nullable=False, server_default=text("0")),
    Column("candidate_count", Integer(), nullable=False, server_default=text("0")),
    Column("brand_changed_count", Integer(), nullable=False, server_default=text("0")),
    Column("reused_count", Integer(), nullable=False, server_default=text("0")),
    Column("existing_reuse_count", Integer(), nullable=False, server_default=text("0")),
    Column("unmatched_count", Integer(), nullable=False, server_default=text("0")),
    Column("analysis_reasons", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_by", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("batch_size between 1 and 1000", name="batch_size_range"),
    CheckConstraint("max_contents between 1 and 10000", name="max_contents_range"),
    CheckConstraint("target_count between 0 and max_contents", name="targets_bounded"),
    CheckConstraint("processed_count between 0 and target_count", name="processed_bounded"),
    CheckConstraint(
        "candidate_count between 0 and processed_count and "
        "brand_changed_count between 0 and processed_count and "
        "reused_count between 0 and processed_count and "
        "existing_reuse_count between 0 and processed_count and "
        "unmatched_count between 0 and processed_count",
        name="counters_bounded",
    ),
    CheckConstraint("jsonb_typeof(catalog_snapshot) = 'object'", name="catalog_object"),
    CheckConstraint("jsonb_typeof(analysis_reasons) = 'object'", name="reasons_object"),
    CheckConstraint("char_length(created_by) between 1 and 200", name="actor_length"),
    info={"owner": "content"},
)

content_consistency_repair_targets_table = Table(
    "content_consistency_repair_targets",
    metadata,
    Column("run_id", Uuid(), ForeignKey("content_consistency_repair_runs.id"), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    info={"owner": "content"},
)
