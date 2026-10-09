"""Content Owner 的按媒体位置播放准备状态；URL 仍唯一保存在 content_media。"""

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

content_media_playback_states_table = Table(
    "content_media_playback_states",
    metadata,
    Column("content_id", Uuid(), primary_key=True),
    Column("position", Integer(), primary_key=True),
    Column("identity_token", Text(), nullable=False),
    Column("source_revision", Text(), nullable=False),
    Column("generation", Integer(), nullable=False),
    Column("state", Text(), nullable=False),
    Column("job_id", Uuid(), ForeignKey("jobs.id")),
    Column("run_id", Uuid(), ForeignKey("collection_runs.id")),
    Column("obtained_at", DateTime(timezone=True)),
    Column("explicit_expires_at", DateTime(timezone=True)),
    Column("failure_code", Text()),
    Column("failure_source_revision", Text()),
    Column("cooldown_until", DateTime(timezone=True)),
    ForeignKeyConstraint(
        ["content_id", "position"],
        ["content_media.content_id", "content_media.position"],
        ondelete="CASCADE",
    ),
    CheckConstraint("generation >= 0", name="generation_nonnegative"),
    CheckConstraint("state in ('ready','preparing','unavailable')", name="state_allowed"),
    info={"owner": "content"},
)
