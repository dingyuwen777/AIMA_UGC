"""建立身份映射与 AIMA 会话表。

建立 4 张表（Owner：`identity`）：

    identity_principals            AIMA 内部稳定身份
    identity_external_identities   外部身份 → AIMA 身份的映射
    identity_login_states          OAuth state（一次性，只存 hash）
    identity_sessions              AIMA 会话（只存 token 的 hash）

**不修改任何历史 Migration**：`down_revision` 指向当时的 head `20260913_0052`。
（本迁移文件当时**尚未提交入库**，故补列时直接改本文件，不新建第二个迁移。）

本迁移与 `backend/src/aima_ugc/modules/identity/tables.py` **逐列一致**，
`alembic check` 必须保持 `No new upgrade operations`。

Revision ID: 20260917_0053
Revises: 20260913_0052
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0053"
down_revision: str | Sequence[str] | None = "20260913_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """建立身份映射（Provider-neutral Principal）与会话持久化。"""

    op.create_table(
        "identity_principals",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(display_name) > 0",
            name=op.f("ck_identity_principals_display_name_nonempty"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_principals")),
    )
    op.create_table(
        "identity_external_identities",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("principal_id", sa.Text(), nullable=False),
        # 哪家企业（本期单企业，仍保留列，便于将来多企业接入时不必改身份模型）。
        sa.Column("connector_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_subject", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(provider) > 0",
            name=op.f("ck_identity_external_identities_provider_nonempty"),
        ),
        sa.CheckConstraint(
            "char_length(provider_subject) > 0",
            name=op.f("ck_identity_external_identities_provider_subject_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["identity_principals.id"],
            name=op.f("fk_identity_external_identities_principal_id_identity_principals"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_external_identities")),
        # ⚠️ 本表的核心约束：同一企业下同一外部身份只能指向一个 AIMA Principal。
        # `connector_id` 必须 NOT NULL —— PostgreSQL 的 UNIQUE 不比较 NULL，
        # 该列一旦可空，多条 NULL 行互不冲突，这个约束就形同虚设。
        sa.UniqueConstraint(
            "connector_id",
            "provider_subject",
            name=op.f("uq_identity_external_identities_connector_id_provider_subject"),
        ),
    )
    op.create_index(
        "ix_identity_external_identities_principal_id",
        "identity_external_identities",
        ["principal_id"],
        unique=False,
    )
    op.create_table(
        "identity_login_states",
        sa.Column("state_hash", sa.Text(), nullable=False),
        # 这次登录属于哪家企业（本期单企业，暂不填写 → **可空**）。
        # ⚠️ 刻意不加 ForeignKey：本期还没有 identity_connectors 表可引用，
        # 加了外键迁移会直接失败。等多企业阶段再单独迁移补齐。
        sa.Column("connector_id", sa.Text(), nullable=True),
        sa.Column("return_to", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(state_hash) > 0",
            name=op.f("ck_identity_login_states_state_hash_nonempty"),
        ),
        sa.PrimaryKeyConstraint("state_hash", name=op.f("pk_identity_login_states")),
    )
    op.create_table(
        "identity_sessions",
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("principal_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("department_id", sa.Text(), nullable=True),
        sa.Column("department_name", sa.Text(), nullable=True),
        # 判角色时命中的飞书用户组 ID（多个用逗号分隔的文本），用于事后留痕。
        sa.Column("feishu_group_ids", sa.Text(), nullable=True),
        # 上一次判出来的角色（角色刷新时记下旧角色，供变更审计）。
        sa.Column("role_snapshot", sa.Text(), nullable=True),
        # 上一次向飞书核对角色/权限的时间（方案 §2.3：会话每 8 小时刷新角色）。
        # NOT NULL 必须配 server_default，否则已有数据的库加列会报 NOT NULL 违反。
        sa.Column(
            "authorization_checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        # 角色只有两种（AIMA 决策 Y）。
        sa.CheckConstraint(
            "role in ('administrator', 'user')",
            name=op.f("ck_identity_sessions_role_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(display_name) > 0",
            name=op.f("ck_identity_sessions_display_name_nonempty"),
        ),
        # 只允许 64 位 SHA-256 十六进制落库：明文令牌会被数据库直接拒绝。
        sa.CheckConstraint(
            "char_length(token_hash) = 64",
            name=op.f("ck_identity_sessions_token_hash_sha256"),
        ),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["identity_principals.id"],
            name=op.f("fk_identity_sessions_principal_id_identity_principals"),
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_identity_sessions")),
    )
    op.create_index(
        "ix_identity_sessions_principal_id",
        "identity_sessions",
        ["principal_id"],
        unique=False,
    )


def downgrade() -> None:
    """按外键依赖顺序回滚：先删引用方，再删被引用的 `identity_principals`。

    本次新增的 4 列（`identity_sessions.authorization_checked_at` /
    `feishu_group_ids` / `role_snapshot`，`identity_login_states.connector_id`）
    都随 `op.create_table` 一起建，因此 `op.drop_table` 会连列一起删掉 ——
    **无需**再写 `op.drop_column`（那会和 drop_table 重复，属多余动作）。
    回滚后 4 张 `identity_*` 表全部消失。
    """

    op.drop_index("ix_identity_sessions_principal_id", table_name="identity_sessions")
    op.drop_table("identity_sessions")
    op.drop_table("identity_login_states")
    op.drop_index(
        "ix_identity_external_identities_principal_id",
        table_name="identity_external_identities",
    )
    op.drop_table("identity_external_identities")
    op.drop_table("identity_principals")
