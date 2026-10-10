"""增加有界历史一致性修复范围及检查点；不扫描或改写历史 Content。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_0084"
down_revision: str | Sequence[str] | None = "20261009_0083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DDL = """
CREATE TABLE content_consistency_repair_runs (
    id UUID NOT NULL,
    job_id UUID NOT NULL,
    catalog_snapshot JSONB NOT NULL,
    source_collection_run_id UUID,
    checkpoint_content_id UUID,
    batch_size INTEGER NOT NULL,
    max_contents INTEGER NOT NULL,
    target_count INTEGER NOT NULL,
    processed_count INTEGER DEFAULT 0 NOT NULL,
    candidate_count INTEGER DEFAULT 0 NOT NULL,
    brand_changed_count INTEGER DEFAULT 0 NOT NULL,
    reused_count INTEGER DEFAULT 0 NOT NULL,
    existing_reuse_count INTEGER DEFAULT 0 NOT NULL,
    unmatched_count INTEGER DEFAULT 0 NOT NULL,
    analysis_reasons JSONB DEFAULT '{}'::jsonb NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_content_consistency_repair_runs PRIMARY KEY (id),
    CONSTRAINT ck_content_consistency_repair_runs_batch_size_range
        CHECK (batch_size between 1 and 1000),
    CONSTRAINT ck_content_consistency_repair_runs_max_contents_range
        CHECK (max_contents between 1 and 10000),
    CONSTRAINT ck_content_consistency_repair_runs_targets_bounded
        CHECK (target_count between 0 and max_contents),
    CONSTRAINT ck_content_consistency_repair_runs_processed_bounded
        CHECK (processed_count between 0 and target_count),
    CONSTRAINT ck_content_consistency_repair_runs_counters_bounded
        CHECK (candidate_count between 0 and processed_count and
               brand_changed_count between 0 and processed_count and
               reused_count between 0 and processed_count and
               existing_reuse_count between 0 and processed_count and
               unmatched_count between 0 and processed_count),
    CONSTRAINT ck_content_consistency_repair_runs_catalog_object
        CHECK (jsonb_typeof(catalog_snapshot) = 'object'),
    CONSTRAINT ck_content_consistency_repair_runs_reasons_object
        CHECK (jsonb_typeof(analysis_reasons) = 'object'),
    CONSTRAINT ck_content_consistency_repair_runs_actor_length
        CHECK (char_length(created_by) between 1 and 200),
    CONSTRAINT uq_content_consistency_repair_runs_job_id UNIQUE (job_id),
    CONSTRAINT fk_content_consistency_repair_runs_job_id_jobs
        FOREIGN KEY(job_id) REFERENCES jobs (id),
    CONSTRAINT fk_content_consistency_repair_runs_source_collection_ru_526a
        FOREIGN KEY(source_collection_run_id) REFERENCES collection_runs (id)
)
"""

TARGET_DDL = """
CREATE TABLE content_consistency_repair_targets (
    run_id UUID NOT NULL,
    content_id UUID NOT NULL,
    CONSTRAINT pk_content_consistency_repair_targets PRIMARY KEY (run_id, content_id),
    CONSTRAINT fk_content_consistency_repair_targets_run_id_content_co_a4b2
        FOREIGN KEY(run_id) REFERENCES content_consistency_repair_runs (id),
    CONSTRAINT fk_content_consistency_repair_targets_content_id_contents
        FOREIGN KEY(content_id) REFERENCES contents (id)
)
"""


def upgrade() -> None:
    """只扩展结构；旧 Worker 不领取新协议，历史修复由显式运维命令触发。"""
    op.execute(sa.text(DDL))
    op.execute(sa.text(TARGET_DDL))


def downgrade() -> None:
    """代码回滚前先取消或排空新修复 Job；已有 Content/Evidence/Result 不改写。"""
    op.drop_table("content_consistency_repair_targets")
    op.drop_table("content_consistency_repair_runs")
