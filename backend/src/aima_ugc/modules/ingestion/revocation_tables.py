"""Data Import Campaign 撤销事实与 Content Version 追溯表。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Table,
    Text,
    Uuid,
)

from aima_ugc.platform.database.metadata import metadata


historical_import_campaign_revocations_table = Table(
    "historical_import_campaign_revocations",
    metadata,
    Column(
        "campaign_id",
        Uuid(),
        ForeignKey("historical_import_campaigns.id"),
        primary_key=True,
    ),
    Column("actor_ref", Text(), nullable=False),
    Column("request_id", Text()),
    Column("reason", Text()),
    Column("affected_content_count", Integer(), nullable=False),
    Column("hidden_content_count", Integer(), nullable=False),
    Column("retained_shared_content_count", Integer(), nullable=False),
    Column("unreversible_content_count", Integer(), nullable=False, server_default="0"),
    Column("revoked_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("char_length(actor_ref) > 0", name="actor_ref_nonempty"),
    CheckConstraint("reason is null or char_length(reason) > 0", name="reason_nonempty"),
    CheckConstraint(
        "affected_content_count >= 0 and hidden_content_count >= 0 "
        "and retained_shared_content_count >= 0 and unreversible_content_count >= 0",
        name="counts_nonnegative",
    ),
    CheckConstraint(
        "hidden_content_count + retained_shared_content_count = affected_content_count",
        name="impact_counts_consistent",
    ),
    CheckConstraint(
        "unreversible_content_count <= affected_content_count",
        name="unreversible_within_affected",
    ),
    CheckConstraint(
        "unreversible_content_count = 0",
        name="committed_revocation_fully_reversible",
    ),
    info={"owner": "ingestion"},
)

historical_import_revocation_content_versions_table = Table(
    "historical_import_revocation_content_versions",
    metadata,
    Column(
        "campaign_id",
        Uuid(),
        ForeignKey("historical_import_campaign_revocations.campaign_id"),
        primary_key=True,
    ),
    Column("content_id", Uuid(), ForeignKey("contents.id"), primary_key=True),
    Column("version_no", Integer(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["content_id", "version_no"],
        ["content_versions.content_id", "content_versions.version_no"],
        name="fk_import_revocation_content_version",
    ),
    CheckConstraint("version_no >= 1", name="version_no_positive"),
    info={"owner": "ingestion"},
)


__all__ = [
    "historical_import_campaign_revocations_table",
    "historical_import_revocation_content_versions_table",
]
