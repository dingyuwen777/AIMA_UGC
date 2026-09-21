"""身份映射与 AIMA 会话表（Owner：`identity`）。

════════ 为什么需要「映射表」而不是直接用飞书 ID ════════

AIMA 的长期门禁（`docs/blueprint/07` 决策 Y）要求：**业务表不以 `feishu_open_id`、
`union_id` 等 Provider 私有身份作公共主键**。所以身份分两层：

    飞书身份（union_id / open_id）
        ↓  写进 identity_external_identities（带 connector_id）
        ↓  UNIQUE(connector_id, provider_subject)
    AIMA Principal（identity_principals.id ← AIMA 自己生成的字符串 ID）
        ↓  Principal.principal_id
    业务表（notification_inbox_items.principal_id 等）

`UNIQUE(connector_id, provider_subject)` 是这套设计的**关键**：它保证
「同一企业下，同一飞书身份只映射到一个 AIMA Principal」。

════════ 四张表的分工 ════════

    identity_principals             AIMA 内部稳定身份
    identity_external_identities    外部身份 → AIMA 身份的映射（本单核心）
    identity_login_states           OAuth state（一次性，只存 hash）
    identity_sessions               AIMA 会话（**只存 token 的 hash**）

════════ 列可空性的取舍（非显然，必须解释）════════

- `connector_id` 设为 **NOT NULL**：PostgreSQL 的 UNIQUE 约束**不比较 NULL**
  （多个 NULL 互不冲突），若该列可空，唯一约束就形同虚设；OAuth state 同样必须
  绑定明确企业，单企业也使用 App ID 派生的稳定 Connector ID。
- `id` 用 `Text()`（应用侧生成 `uuid4().hex` 的 32 位十六进制字符串），不用自增：
  自增会把「身份标识」暴露成可枚举序号，且跨库迁移/合并时更容易撞号。
- 时间列统一 `DateTime(timezone=True)`（`timestamptz`），语义是绝对时间点。
- `identity_sessions.authorization_checked_at` 是 **NOT NULL 且带 `now()` 默认值**：
  它记的是"上次核对角色的时间"，语义上每条会话都必须有值；给默认值是为了
  已有数据的库加列时不报 NOT NULL 违反。
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Table,
    Text,
    UniqueConstraint,
    func,
)

from aima_ugc.platform.database.metadata import metadata

# SHA-256 十六进制摘要固定 64 字符；用它当 CHECK 可以防止"把明文令牌写进 hash 列"。
_SHA256_HEX_LENGTH = 64

identity_principals_table = Table(
    "identity_principals",
    metadata,
    Column("id", Text(), primary_key=True),
    Column("display_name", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True)),
    CheckConstraint("char_length(display_name) > 0", name="display_name_nonempty"),
    info={"owner": "identity"},
)

identity_external_identities_table = Table(
    "identity_external_identities",
    metadata,
    Column("id", Text(), primary_key=True),
    Column(
        "principal_id",
        Text(),
        ForeignKey("identity_principals.id"),
        nullable=False,
    ),
    # 哪家企业；多 Connector 依靠该列隔离相同的 Provider Subject。
    Column("connector_id", Text(), nullable=False),
    Column("provider", Text(), nullable=False),
    Column("provider_subject", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True)),
    # ⚠️ 本表的核心约束：同一企业下同一外部身份只能指向一个 AIMA Principal。
    UniqueConstraint("connector_id", "provider_subject"),
    CheckConstraint("char_length(provider) > 0", name="provider_nonempty"),
    CheckConstraint("char_length(provider_subject) > 0", name="provider_subject_nonempty"),
    Index("ix_identity_external_identities_principal_id", "principal_id"),
    info={"owner": "identity"},
)

identity_login_states_table = Table(
    "identity_login_states",
    metadata,
    Column("state_hash", Text(), primary_key=True),
    # 所有 state 都绑定 Connector ID；当前没有持久 identity_connectors 表，故不建虚假外键。
    Column("connector_id", Text(), nullable=False),
    Column("return_to", Text()),
    # 发起登录的客户端 IP（可空：取不到时留空，不因此拒绝登录）。
    # 用途只有一个 —— **登录入口的 IP 维度限流**（S8）：按"过去 60 秒内同一 IP
    # 发起了多少次登录"计数。它是安全用途的运维数据，不参与身份判定。
    Column("client_ip", Text()),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("consumed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("char_length(state_hash) > 0", name="state_hash_nonempty"),
    info={"owner": "identity"},
)

# 限流查询专用索引：`(client_ip, created_at)` 让"过去 60 秒内同一 IP 的次数"
# 走索引范围扫描，而不是全表扫。`created_at` 单列索引服务全局维度限流。
Index(
    "ix_identity_login_states_client_ip_created",
    identity_login_states_table.c.client_ip,
    identity_login_states_table.c.created_at,
)
Index(
    "ix_identity_login_states_created",
    identity_login_states_table.c.created_at,
)

identity_sessions_table = Table(
    "identity_sessions",
    metadata,
    Column("token_hash", Text(), primary_key=True),
    Column(
        "principal_id",
        Text(),
        ForeignKey("identity_principals.id"),
        nullable=False,
    ),
    Column("display_name", Text(), nullable=False),
    Column("avatar_url", Text()),
    # 角色只有两种：administrator / user（DB 层 CHECK，见 AIMA 决策 Y）。
    Column("role", Text(), nullable=False),
    # 部门只作展示用，**不进 Principal 契约**（避免改动公共 Contract）。
    Column("department_id", Text()),
    Column("department_name", Text()),
    # 判角色时命中的飞书用户组 ID（多个用逗号分隔的文本）。
    # 用途是**留痕**：事后能回答"他当时凭什么被判成管理员"。
    # 用 Text 而不是 PostgreSQL 数组，是照仓库既有风格 —— 同类"只读留痕/快照"
    # 字段（`provider_configs` 等）也用 Text，避免为可读性引入类型差异。
    Column("feishu_group_ids", Text()),
    # 上一次判出来的角色。角色刷新时把**旧角色**记下来，供角色变更审计。
    Column("role_snapshot", Text()),
    # 记录最近一次完成飞书授权判定的时间，为未来受控刷新提供持久事实。
    # 当前版本不会在会话存续期自动回查飞书，远端撤权最迟在会话过期后生效；
    # 不能用这个列的存在宣称刷新链路已经实现。
    # `server_default=func.now()` 保证首次签发会话时该事实非空。
    Column(
        "authorization_checked_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    CheckConstraint("role in ('administrator', 'user')", name="role_allowed"),
    CheckConstraint("char_length(display_name) > 0", name="display_name_nonempty"),
    # 只有 64 位 SHA-256 十六进制才允许落库；明文令牌（长度通常不等于 64）会被直接拒绝。
    CheckConstraint(
        f"char_length(token_hash) = {_SHA256_HEX_LENGTH}",
        name="token_hash_sha256",
    ),
    Index("ix_identity_sessions_principal_id", "principal_id"),
    info={"owner": "identity"},
)

__all__ = [
    "identity_external_identities_table",
    "identity_login_states_table",
    "identity_principals_table",
    "identity_sessions_table",
]
