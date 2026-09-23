"""建立身份映射与 AIMA 会话表。

建立 4 张表（Owner：`identity`）：

    identity_principals            AIMA 内部稳定身份
    identity_external_identities   外部身份 → AIMA 身份的映射
    identity_login_states          OAuth state（一次性，只存 hash）
    identity_sessions              AIMA 会话（只存 token 的 hash）

本 Migration 是身份能力首次进入 canonical 主分支的完整 Schema，接在当前真实 head
`20260921_0055` 之后。交付包中未进入主分支的旧迁移编号不构成项目历史事实，不能与
已经存在的声音广场 Migration 形成平行 head 或重复 revision。

本迁移与 `backend/src/aima_ugc/modules/identity/tables.py` **逐列一致**，
`alembic check` 必须保持 `No new upgrade operations`。

Revision ID: 20260921_0056
Revises: 20260921_0055
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0056"
down_revision: str | Sequence[str] | None = "20260921_0055"
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
        # 哪家企业；多 Connector 依靠该列隔离相同的 Provider Subject。
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
        # 所有 state 都绑定 Connector ID；当前没有持久 identity_connectors 表，故不建虚假外键。
        sa.Column("connector_id", sa.Text(), nullable=False),
        sa.Column("return_to", sa.Text(), nullable=True),
        sa.Column("client_ip", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(state_hash) > 0",
            name=op.f("ck_identity_login_states_state_hash_nonempty"),
        ),
        sa.PrimaryKeyConstraint("state_hash", name=op.f("pk_identity_login_states")),
    )
    op.create_index(
        "ix_identity_login_states_client_ip_created",
        "identity_login_states",
        ["client_ip", "created_at"],
    )
    op.create_index(
        "ix_identity_login_states_created",
        "identity_login_states",
        ["created_at"],
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
        # 最近一次完成飞书授权判定的时间；当前版本不自动回查飞书。
        # NOT NULL 配 server_default，保证首次签发会话时该事实非空。
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

    所有身份列与登录限流索引都由本 Migration 首次建立；回滚时先删除显式索引，
    再按外键依赖顺序删除表。
    回滚后 4 张 `identity_*` 表全部消失。
    """

    op.drop_index("ix_identity_sessions_principal_id", table_name="identity_sessions")
    op.drop_table("identity_sessions")
    op.drop_index("ix_identity_login_states_created", table_name="identity_login_states")
    op.drop_index(
        "ix_identity_login_states_client_ip_created",
        table_name="identity_login_states",
    )
    op.drop_table("identity_login_states")
    op.drop_index(
        "ix_identity_external_identities_principal_id",
        table_name="identity_external_identities",
    )
    op.drop_table("identity_external_identities")
    op.drop_table("identity_principals")
