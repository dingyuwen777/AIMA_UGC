"""`identity_login_states` 增加 `client_ip` 列与两个限流索引。

════════ 为什么加这一列 ════════

方案 §6.0 **S8** 要求登录入口**双轨限流**（IP 维度 + 全局维度），
§七 **C2** 进一步要求"计数必须跨进程共享（用数据库计数）"。

本模块的限流以「过去 60 秒内 `identity_login_states` 的行数」为计数 ——
但该表原先**没有来源 IP**，因此 IP 维度无法实现。本迁移补上：

- `client_ip`（可空）：发起登录的来源地址。**刻意可空** ——
  取不到 IP 不是拒绝登录的理由（反向代理配置差异、测试环境都可能取不到），
  此时仍受全局阈值保护。
- `ix_identity_login_states_client_ip_created`：让"同一 IP 在过去 60 秒的次数"
  走索引范围扫描，而不是每次限流都全表扫。
- `ix_identity_login_states_created`：服务全局维度的同一个查询。

════════ 影响 ════════

- 只加列与索引，**不改既有列**；已有行的 `client_ip` 为 `NULL`，
  限流查询对它们是"无 IP 的历史记录"，不影响全局计数。
- `downgrade()` 删索引与列。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0055"
down_revision: str | None = "20260920_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """加 `client_ip` 列与两个限流索引。"""

    op.add_column(
        "identity_login_states",
        sa.Column("client_ip", sa.Text(), nullable=True),
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


def downgrade() -> None:
    """删索引与列（顺序与 upgrade 相反）。"""

    op.drop_index("ix_identity_login_states_created", table_name="identity_login_states")
    op.drop_index(
        "ix_identity_login_states_client_ip_created",
        table_name="identity_login_states",
    )
    op.drop_column("identity_login_states", "client_ip")
