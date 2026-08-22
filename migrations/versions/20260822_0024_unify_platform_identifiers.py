"""统一五个平台机器标识并移除小红书双值语义。

Revision ID: 20260822_0024
Revises: 20260821_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "20260822_0024"
down_revision: str | Sequence[str] | None = "20260821_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED = "('xiaohongshu','douyin','weibo','bilibili','kuaishou')"
_SCOPE_ALLOWED = "('all','xiaohongshu','douyin','weibo','bilibili','kuaishou')"
_OLD_REPLAY = "collection.xhs.raw-replay.v1"
_NEW_REPLAY = "collection.xiaohongshu.raw-replay.v1"


def _exists(connection: Connection, sql: str) -> bool:
    return bool(connection.scalar(sa.text(f"SELECT EXISTS ({sql})")))


def _assert_no_identity_conflicts(connection: Connection) -> None:
    checks = {
        "accounts": """
            SELECT 1 FROM accounts old
            JOIN accounts new ON new.external_account_id = old.external_account_id
            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'
        """,
        "contents": """
            SELECT 1 FROM contents old
            JOIN contents new ON new.external_content_id = old.external_content_id
            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'
        """,
        "collection_plan_platforms": """
            SELECT 1 FROM collection_plan_platforms old
            JOIN collection_plan_platforms new ON new.plan_id = old.plan_id
            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'
        """,
        "collection_scopes": """
            SELECT 1 FROM collection_scopes old
            JOIN collection_scopes new
              ON new.run_id = old.run_id
             AND new.source_type = old.source_type
             AND new.source_value = old.source_value
             AND new.operation_group = old.operation_group
            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'
        """,
        "keyword_pack_items": """
            SELECT 1 FROM keyword_pack_items old
            JOIN keyword_pack_items new
              ON new.pack_id = old.pack_id AND new.keyword_id = old.keyword_id
            WHERE old.platform = 'xhs' AND new.platform = 'xiaohongshu'
        """,
        "jobs": f"""
            SELECT 1 FROM jobs old
            JOIN jobs new ON new.internal_idempotency_key = old.internal_idempotency_key
            WHERE old.job_type = '{_OLD_REPLAY}' AND new.job_type = '{_NEW_REPLAY}'
        """,
    }
    conflicts = [name for name, sql in checks.items() if _exists(connection, sql)]
    if conflicts:
        raise RuntimeError(
            "平台标识迁移冲突：同一业务身份同时存在旧值和正式值：" + ", ".join(conflicts)
        )


def _rewrite_run_platforms(old: str, new: str) -> None:
    op.execute(
        sa.text(
            """
            UPDATE collection_runs
            SET config_snapshot = jsonb_set(
                config_snapshot,
                '{platforms}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN jsonb_typeof(item) = 'object' AND item->>'platform' = :old
                                THEN jsonb_set(item, '{platform}', to_jsonb(CAST(:new AS text)))
                            WHEN item = to_jsonb(CAST(:old AS text))
                                THEN to_jsonb(CAST(:new AS text))
                            ELSE item
                        END
                        ORDER BY ord
                    )
                    FROM jsonb_array_elements(config_snapshot->'platforms')
                         WITH ORDINALITY AS elements(item, ord)
                )
            )
            WHERE jsonb_typeof(config_snapshot->'platforms') = 'array'
              AND EXISTS (
                  SELECT 1
                  FROM jsonb_array_elements(config_snapshot->'platforms') AS elements(item)
                  WHERE (jsonb_typeof(item) = 'object' AND item->>'platform' = :old)
                     OR item = to_jsonb(CAST(:old AS text))
              )
            """
        ).bindparams(old=old, new=new)
    )


def _create_platform_constraints() -> None:
    # 0023 中这些 allowed 约束尚不存在。这里直接发出最终物理 DDL，避免
    # 把已经按 naming convention 格式化的名称再次交给 Alembic 命名包装。
    op.execute(
        f"ALTER TABLE accounts ADD CONSTRAINT ck_accounts_platform_allowed "
        f"CHECK (platform in {_ALLOWED})"
    )
    op.execute(
        f"ALTER TABLE contents ADD CONSTRAINT ck_contents_platform_allowed "
        f"CHECK (platform in {_ALLOWED})"
    )
    op.execute(
        "ALTER TABLE collection_plan_platforms "
        "ADD CONSTRAINT ck_collection_plan_platforms_platform_allowed "
        f"CHECK (platform in {_ALLOWED})"
    )
    op.execute(
        "ALTER TABLE collection_scopes "
        "ADD CONSTRAINT ck_collection_scopes_platform_allowed "
        f"CHECK (platform in {_ALLOWED})"
    )
    op.execute(
        "ALTER TABLE keyword_pack_items "
        "ADD CONSTRAINT ck_keyword_pack_items_platform_scope_allowed "
        f"CHECK (platform_scope in {_SCOPE_ALLOWED})"
    )


def upgrade() -> None:
    connection = op.get_bind()
    _assert_no_identity_conflicts(connection)

    op.drop_constraint(
        op.f("ck_collection_plan_platforms_platform_nonempty"),
        "collection_plan_platforms",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_keyword_pack_items_platform_nonempty"),
        "keyword_pack_items",
        type_="check",
    )

    for table in ("accounts", "contents", "collection_plan_platforms", "collection_scopes"):
        op.execute(f"UPDATE {table} SET platform = 'xiaohongshu' WHERE platform = 'xhs'")

    op.execute("UPDATE keyword_pack_items SET platform = 'xiaohongshu' WHERE platform = 'xhs'")
    op.execute(
        "UPDATE collection_candidate_ingestions "
        "SET canonical_identity = 'xiaohongshu:' || substring(canonical_identity from 5) "
        "WHERE canonical_identity LIKE 'xhs:%'"
    )
    _rewrite_run_platforms("xhs", "xiaohongshu")

    op.execute(
        sa.text(
            """
            UPDATE jobs
            SET job_type = CASE WHEN job_type = :old THEN :new ELSE job_type END,
                payload_version = CASE
                    WHEN payload_version = :old THEN :new
                    ELSE payload_version
                END,
                payload = CASE
                    WHEN payload->>'schema_version' = :old
                    THEN jsonb_set(payload, '{schema_version}', to_jsonb(CAST(:new AS text)))
                    ELSE payload
                END
            WHERE job_type = :old OR payload_version = :old OR payload->>'schema_version' = :old
            """
        ).bindparams(old=_OLD_REPLAY, new=_NEW_REPLAY)
    )

    op.alter_column(
        "keyword_pack_items",
        "platform",
        new_column_name="platform_scope",
        existing_type=sa.Text(),
        existing_nullable=False,
    )
    _create_platform_constraints()


def downgrade() -> None:
    # 平台身份合并是不可逆数据归一化：升级后无法仅凭当前行可靠恢复来源。
    # Downgrade 只回退 Schema/字段名；真正的数据回滚必须恢复升级前数据库备份。
    op.drop_constraint(
        op.f("ck_keyword_pack_items_platform_scope_allowed"),
        "keyword_pack_items",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_collection_scopes_platform_allowed"),
        "collection_scopes",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_collection_plan_platforms_platform_allowed"),
        "collection_plan_platforms",
        type_="check",
    )
    op.drop_constraint(op.f("ck_contents_platform_allowed"), "contents", type_="check")
    op.drop_constraint(op.f("ck_accounts_platform_allowed"), "accounts", type_="check")
    op.alter_column(
        "keyword_pack_items",
        "platform_scope",
        new_column_name="platform",
        existing_type=sa.Text(),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_keyword_pack_items_platform_nonempty"),
        "keyword_pack_items",
        "char_length(platform) > 0",
    )
    op.create_check_constraint(
        op.f("ck_collection_plan_platforms_platform_nonempty"),
        "collection_plan_platforms",
        "char_length(platform) > 0",
    )
