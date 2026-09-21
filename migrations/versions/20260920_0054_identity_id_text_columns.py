"""identity 身份列由 uuid 改为 text，与 Principal 契约和既有表保持一致。

════════ 为什么改 ════════

`identity_principals.id` 等 6 个身份列最初建为 `uuid`，但：

1. `Principal.principal_id` 的契约类型是 `str`（`modules/identity/models.py`），
   `text` 与该契约一致；`uuid` 比契约更严，属于收窄。
2. 既有表 `notification_inbox_items.principal_id` 已经是 `text`，
   身份 ID 在库内应保持同一种表示。
3. `DevelopmentIdentityResolver` 的开发身份是 `local-administrator`，
   **不是合法 UUID**；`uuid` 列装不下它，会给将来的本地开发/测试留下隐患。

════════ 为什么可以无损转换 ════════

应用侧一直用 `uuid4().hex` 生成 32 位十六进制字符串写库；
PostgreSQL 的 `uuid` 类型在文本表示下**本来就是同样的 32 位十六进制**。
因此 `ALTER ... TYPE text USING c::text` 只改变存储类型，
**不改变任何已有值的内容**。

════════ 影响 ════════

- 列类型 `uuid` → `text`；已有值逐字保留。
- 外键关系不变（`identity_sessions.principal_id` → `identity_principals.id`）。
- `downgrade()` 通过 `USING c::uuid` 转回；若届时库里存在非 UUID 文本
  （例如开发身份），转换会失败 —— 这是**预期行为**，说明该数据本就不该存进 uuid 列。

Revision ID: 20260920_0054
Revises: 20260917_0053
Create Date: 2026-09-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260920_0054"
down_revision: str | None = "20260917_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (表名, 列名)：从原迁移 20260917_0053 继承下来的 6 个 uuid 列。
_UUID_TO_TEXT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("identity_principals", "id"),
    ("identity_external_identities", "id"),
    ("identity_external_identities", "principal_id"),
    ("identity_external_identities", "connector_id"),
    ("identity_login_states", "connector_id"),
    ("identity_sessions", "principal_id"),
)

# 指向 `identity_principals.id` 的两条外键：改列类型前必须先摘掉。
# PG 不允许"引用列与新类型不兼容"的状态存在，因此顺序必须是
# 删外键 → 改两侧列 → 重建外键。
#
# ⚠️ 名字用的是**数据库里的真实名**，不是原迁移里的声明名。
# 原迁移声明的 `fk_identity_external_identities_principal_id_identity_principals`
# 有 72 字符，**超过 PostgreSQL 的 63 字符标识符上限**，建表时被 PG 截断成
# `..._identity_p_8b12`（60 字符）。SQLAlchemy 在 `create_foreign_key` 时会
# 对超过 63 字符的名字直接报 `IdentifierError`，所以这里必须用截断后的名字，
# 否则迁移无法在已有库上重放。
_FOREIGN_KEYS: tuple[tuple[str, str, str, str], ...] = (
    (
        "identity_external_identities",
        "principal_id",
        "identity_principals",
        "fk_identity_external_identities_principal_id_identity_p_8b12",
    ),
    (
        "identity_sessions",
        "principal_id",
        "identity_principals",
        "fk_identity_sessions_principal_id_identity_principals",
    ),
)


def upgrade() -> None:
    """把 6 个身份列由 `uuid` 改为 `text`，并把值规范化成 32 位无连字符十六进制。

    ════════ 为什么不是简单 `::text` ════════

    PostgreSQL 的 `uuid` 类型转成文本时带连字符（36 位，标准 UUID 格式）：
        `9887869d-a293-42ca-b21b-8b5f13ff4569`
    而应用侧统一用 `uuid4().hex` 写入（32 位、无连字符）：
        `9887869da29342cab21b8b5f13ff4569`

    若只做 `::text`，同一列会同时存在两种格式 —— 同一身份可能查不出来。
    所以这里先转文本，**再去掉连字符**，让历史值与新写入值同构。

    ════════ 为什么要先摘外键 ════════

    `identity_external_identities.principal_id` 与 `identity_sessions.principal_id`
    都通过外键指向 `identity_principals.id`。PG 不允许被引用列与引用列类型不兼容，
    所以必须先删外键，改完两侧列再重建。
    """

    # ① 摘掉指向 identity_principals.id 的外键（按数据库里的真实名）
    for child_table, _child_col, _parent_table, fk_name in _FOREIGN_KEYS:
        op.drop_constraint(fk_name, child_table, type_="foreignkey")

    # ② 逐列改为 text，并把值规范化成 32 位无连字符形式
    for table, column in _UUID_TO_TEXT_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Text(),
            existing_type=sa.Uuid(),
            postgresql_using=f"{column}::text",
        )
        op.execute(
            sa.text(
                f"UPDATE {table} SET {column} = replace({column}, '-', '') "
                f"WHERE {column} LIKE '%-%'"
            )
        )

    # ③ 按原定义重建外键（两侧都已是 text，可以建立）
    for child_table, child_col, parent_table, fk_name in _FOREIGN_KEYS:
        op.create_foreign_key(
            fk_name,
            child_table,
            parent_table,
            [child_col],
            ["id"],
        )


def downgrade() -> None:
    """把 6 个身份列由 `text` 转回 `uuid`。

    只有当列中所有值都是合法 UUID 文本时才能成功 —— 这正是所需约束：
    一旦存过非 UUID 的开发身份，就不该退回 `uuid` 列。
    """

    # ① 与 upgrade 对称：先摘掉外键（引用列与被引用列同时从 text 转回 uuid）
    for child_table, _child_col, _parent_table, fk_name in _FOREIGN_KEYS:
        op.drop_constraint(fk_name, child_table, type_="foreignkey")

    # ② 补回连字符后转回 uuid
    for table, column in _UUID_TO_TEXT_COLUMNS:
        # PG 的 uuid 输入接受 32 位无连字符形式，这里显式补回标准格式更清晰
        op.execute(
            sa.text(
                f"UPDATE {table} SET {column} = "
                f"substr({column},1,8) || '-' || substr({column},9,4) || '-' || "
                f"substr({column},13,4) || '-' || substr({column},17,4) || '-' || "
                f"substr({column},21,12) "
                f"WHERE char_length({column}) = 32"
            )
        )
        op.alter_column(
            table,
            column,
            type_=sa.Uuid(),
            existing_type=sa.Text(),
            postgresql_using=f"{column}::uuid",
        )

    # ③ 重建外键
    for child_table, child_col, parent_table, fk_name in _FOREIGN_KEYS:
        op.create_foreign_key(
            fk_name,
            child_table,
            parent_table,
            [child_col],
            ["id"],
        )
