"""Stage 8A Processing / Import Batch 与 Provider 来源父级 Schema。"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from aima_ugc.modules.collection.tables import provider_requests_table
from aima_ugc.platform.database.metadata import metadata

processing_import_batches_table = Table(
    "processing_import_batches",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("input_artifact_id", Uuid, ForeignKey("artifacts.id"), nullable=False),
    Column("job_id", Uuid, ForeignKey("jobs.id"), nullable=True, unique=True),
    Column("status", Text, nullable=False),
    Column("stats", JSONB, nullable=False, server_default="{}"),
    Column("error_summary", Text, nullable=True),
    Column("historical_mode", Boolean, nullable=False, server_default="false"),
    Column(
        "historical_campaign_item_id",
        Uuid,
        ForeignKey(
            "historical_import_campaign_items.id",
            name="fk_pib_history_item",
        ),
        nullable=True,
    ),
    Column("historical_policy_version", Text, nullable=True),
    Column(
        "retry_of_batch_id",
        Uuid,
        ForeignKey("processing_import_batches.id", name="fk_pib_retry"),
        nullable=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("status in ('processing','succeeded','failed')", name="status_allowed"),
    CheckConstraint(
        "(historical_campaign_item_id is null and historical_policy_version is null "
        "and retry_of_batch_id is null and not historical_mode) or "
        "(historical_campaign_item_id is not null "
        "and historical_policy_version in "
        "('historical-fill-only.v1','standard-observation.v1') "
        "and historical_mode = "
        "(historical_policy_version = 'historical-fill-only.v1'))",
        name="historical_fields_consistent",
    ),
    info={"owner": "ingestion"},
)


def register_ingestion_schema() -> None:
    """Provider Request 必须恰好属于 Collection Scope 或 Import Batch。"""
    if "import_batch_id" in provider_requests_table.c:
        return
    provider_requests_table.append_column(
        Column(
            "import_batch_id",
            Uuid,
            ForeignKey("processing_import_batches.id"),
            nullable=True,
        )
    )
    provider_requests_table.c.scope_id.nullable = True
    provider_requests_table.append_constraint(
        CheckConstraint(
            "(scope_id is not null and import_batch_id is null) or "
            "(scope_id is null and import_batch_id is not null)",
            name="source_parent_exactly_one",
        )
    )
    provider_requests_table.append_constraint(
        UniqueConstraint(
            provider_requests_table.c.import_batch_id,
            provider_requests_table.c.request_fingerprint,
            name="uq_provider_requests_import_batch_id_request_fingerprint",
        )
    )
    Index(
        "ix_provider_requests_import_batch_id_created_at",
        provider_requests_table.c.import_batch_id,
        provider_requests_table.c.created_at,
    )


register_ingestion_schema()

__all__ = ["processing_import_batches_table", "register_ingestion_schema"]
