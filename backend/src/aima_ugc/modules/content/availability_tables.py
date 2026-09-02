"""第三方内容可用状态的追加式观察表。"""

from sqlalchemy import (
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

content_availability_observations_table = Table(
    "content_availability_observations",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("content_id", Uuid(), ForeignKey("contents.id"), nullable=False),
    Column("content_version", Integer(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("reason_code", Text(), nullable=False),
    Column("evidence_kind", Text(), nullable=False),
    Column("provider_attempt_id", Uuid(), ForeignKey("provider_request_attempts.id")),
    Column("raw_artifact_id", Uuid(), ForeignKey("artifacts.id")),
    Column("safe_summary", Text(), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "content_id", "observed_at", "status", name="uq_content_availability_observation_identity"
    ),
    CheckConstraint(
        "status in ('available','unavailable_confirmed','unavailable_suspected','unknown')",
        name="status_allowed",
    ),
    CheckConstraint(
        "evidence_kind in ('provider_explicit','technical_failure','manual_review')",
        name="evidence_kind_allowed",
    ),
    CheckConstraint(
        "status <> 'unavailable_confirmed' or "
        "(evidence_kind = 'provider_explicit' and "
        "(provider_attempt_id is not null or raw_artifact_id is not null))",
        name="confirmed_evidence",
    ),
    CheckConstraint(
        "evidence_kind <> 'technical_failure' or status in ('unknown','unavailable_suspected')",
        name="technical_status",
    ),
    CheckConstraint("content_version > 0", name="content_version_positive"),
    info={"owner": "content"},
)

__all__ = ["content_availability_observations_table"]
