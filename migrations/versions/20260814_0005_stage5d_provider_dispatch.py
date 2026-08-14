"""收紧 Provider Request 状态并允许终态一次绑定 Raw。

Revision ID: 20260814_0005
Revises: 20260814_0004
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260814_0005"
down_revision: str | Sequence[str] | None = "20260814_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        op.f("ck_provider_requests_status_allowed"),
        "provider_requests",
        "status in ('pending','dispatching','completed','not_sent','unknown')",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION guard_provider_attempt_lineage()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.dispatch_status <> 'reserved'
               AND OLD.provider_request_id IS DISTINCT FROM NEW.provider_request_id THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Provider Attempt 离开 reserved 后 Request 来源不可修改';
            END IF;

            IF OLD.raw_artifact_id IS DISTINCT FROM NEW.raw_artifact_id THEN
                IF OLD.raw_artifact_id IS NOT NULL THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23514',
                        MESSAGE = 'Provider Attempt 已绑定的 Raw 引用不可修改';
                END IF;
                IF NEW.raw_artifact_id IS NULL
                   OR NEW.dispatch_status NOT IN ('completed', 'unknown') THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23514',
                        MESSAGE = 'Provider Attempt 只能在 completed/unknown 终态一次绑定 Raw';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION guard_provider_attempt_lineage()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.dispatch_status <> 'reserved'
               AND ROW(OLD.provider_request_id, OLD.raw_artifact_id)
                   IS DISTINCT FROM
                   ROW(NEW.provider_request_id, NEW.raw_artifact_id) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Provider Attempt 离开 reserved 后来源引用不可修改';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.drop_constraint(
        op.f("ck_provider_requests_status_allowed"),
        "provider_requests",
        type_="check",
    )
