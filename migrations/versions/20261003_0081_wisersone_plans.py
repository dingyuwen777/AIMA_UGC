"""WisersOne 共用计划与调度账本，下载冻结品牌过滤范围。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0081"
down_revision: str | Sequence[str] | None = "20261003_0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("plan_type_allowed", "comment_policy_allowed"):
        op.drop_constraint(op.f(f"ck_collection_plans_{name}"), "collection_plans", type_="check")
    op.create_check_constraint(
        op.f("ck_collection_plans_plan_type_allowed"),
        "collection_plans",
        "plan_type in ('tikhub','wisersone')",
    )
    op.create_check_constraint(
        op.f("ck_collection_plans_comment_policy_allowed"),
        "collection_plans",
        "comment_policy in ('adaptive','full','not_applicable')",
    )
    op.add_column(
        "ingestion_wisersone_downloads",
        sa.Column(
            "filter_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("ingestion_wisersone_downloads", "filter_snapshot", server_default=None)
    op.add_column(
        "ingestion_wisersone_downloads",
        sa.Column("occurrence_id", sa.Uuid(), sa.ForeignKey("collection_schedule_occurrences.id")),
    )
    op.create_unique_constraint(
        op.f("uq_ingestion_wisersone_downloads_occurrence_id"),
        "ingestion_wisersone_downloads",
        ["occurrence_id"],
    )
    _extend_occurrence_consistency()


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM collection_plans WHERE plan_type='wisersone') "
            "OR EXISTS (SELECT 1 FROM ingestion_wisersone_downloads)"
        )
    ):
        raise RuntimeError("存在 WisersOne 计划或下载事实，不能丢弃冻结过滤或调度关系后降级。")
    op.execute("DROP TRIGGER trg_wisersone_occurrence_consistency ON ingestion_wisersone_downloads")
    _extend_occurrence_consistency(wisersone=False)
    op.drop_column("ingestion_wisersone_downloads", "occurrence_id")
    op.drop_column("ingestion_wisersone_downloads", "filter_snapshot")
    for name in ("plan_type_allowed", "comment_policy_allowed"):
        op.drop_constraint(op.f(f"ck_collection_plans_{name}"), "collection_plans", type_="check")
    op.create_check_constraint(
        op.f("ck_collection_plans_plan_type_allowed"), "collection_plans", "plan_type in ('tikhub')"
    )
    op.create_check_constraint(
        op.f("ck_collection_plans_comment_policy_allowed"),
        "collection_plans",
        "comment_policy in ('adaptive','full')",
    )


def _extend_occurrence_consistency(*, wisersone: bool = True) -> None:
    """账本必须关联对应来源的真实执行事实；下载续跑只替换活动 Job。"""
    wise_branch = (
        """
        SELECT count(*), count(*) FILTER (WHERE
            NOT EXISTS (SELECT 1 FROM jobs j WHERE j.id = occurrence_job_id
                AND j.job_type = 'ingestion.wisersone-download.v1'
                AND j.payload->>'download_id' = d.id::text))
        INTO download_count, inconsistent_download_count
        FROM ingestion_wisersone_downloads d WHERE d.occurrence_id = occurrence_uuid;
        IF plan_kind = 'wisersone' THEN
            IF reverse_run_count <> 0 OR
               (occurrence_status = 'enqueued' AND
                (download_count <> 1 OR inconsistent_download_count <> 0)) OR
               (occurrence_status = 'skipped' AND download_count <> 0) THEN
                RAISE EXCEPTION USING ERRCODE = '23514',
                    MESSAGE = 'WisersOne Occurrence 必须关联唯一同初始 Job 的下载事实';
            END IF;
            RETURN;
        ELSIF download_count <> 0 THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'TikHub Occurrence 不允许关联 WisersOne 下载事实';
        END IF;
    """
        if wisersone
        else ""
    )
    op.execute(f"""
        CREATE OR REPLACE FUNCTION assert_collection_occurrence_run_consistency(
            occurrence_uuid uuid)
        RETURNS void LANGUAGE plpgsql AS $$
        DECLARE
            occurrence_status text; occurrence_job_id uuid; plan_kind text;
            reverse_run_count integer; inconsistent_run_count integer;
            download_count integer; inconsistent_download_count integer;
        BEGIN
            IF occurrence_uuid IS NULL THEN RETURN; END IF;
            SELECT o.status, o.job_id, p.plan_type
            INTO occurrence_status, occurrence_job_id, plan_kind
            FROM collection_schedule_occurrences o JOIN collection_plans p ON p.id=o.plan_id
            WHERE o.id=occurrence_uuid;
            IF NOT FOUND THEN RETURN; END IF;
            SELECT count(*), count(*) FILTER (WHERE job_id IS DISTINCT FROM occurrence_job_id
                OR trigger_type <> 'scheduled')
            INTO reverse_run_count, inconsistent_run_count FROM collection_runs
            WHERE occurrence_id=occurrence_uuid;
            {wise_branch}
            IF occurrence_status='enqueued' THEN
                IF reverse_run_count <> 1 OR inconsistent_run_count <> 0 THEN
                    RAISE EXCEPTION USING ERRCODE='23514',
                        MESSAGE='enqueued Occurrence 必须恰有一个同 Job 的 scheduled Run';
                END IF;
            ELSIF occurrence_status='skipped' AND reverse_run_count <> 0 THEN
                RAISE EXCEPTION USING ERRCODE='23514',
                    MESSAGE='skipped Collection Occurrence 不允许关联 Run';
            END IF;
        END; $$
    """)
    if wisersone:
        op.execute("""
            CREATE FUNCTION enforce_wisersone_occurrence_consistency() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                IF TG_OP IN ('UPDATE','DELETE') THEN
                    PERFORM assert_collection_occurrence_run_consistency(OLD.occurrence_id);
                END IF;
                IF TG_OP IN ('INSERT','UPDATE') THEN
                    PERFORM assert_collection_occurrence_run_consistency(NEW.occurrence_id);
                END IF;
                RETURN NULL;
            END; $$;
            CREATE CONSTRAINT TRIGGER trg_wisersone_occurrence_consistency
                AFTER INSERT OR UPDATE OR DELETE ON ingestion_wisersone_downloads
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
                EXECUTE FUNCTION enforce_wisersone_occurrence_consistency();
        """)
    else:
        op.execute("DROP FUNCTION enforce_wisersone_occurrence_consistency()")
