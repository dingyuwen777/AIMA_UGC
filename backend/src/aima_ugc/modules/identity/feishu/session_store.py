"""AIMA 会话（Session）的存取：**只存 hash，不存明文令牌**。

════════ 为什么必须有这一层 ════════

飞书的 `user_access_token` **不能当 AIMA 的登录态**：
它有效期只有 2 小时，且是飞书侧的凭证。正确做法是自己发一枚随机 Session Token
交给浏览器（Cookie），数据库里**只存它的 hash**。

这样即使数据库被拖走，攻击者拿到的也只是 hash —— **无法反推出可用的令牌**。
（`token_hash` 列还有 CHECK 约束要求长度 64，明文令牌会被数据库直接拒绝。）

════════ hash 用什么 ════════

SHA-256（标准库 `hashlib`），**不加盐、不用 bcrypt**。这是刻意的：

- Session Token 是**高熵随机值**（本模块默认 32 字节 ≈ 256 位），
  不存在"弱口令字典"可猜，加盐对暴力破解没有实际增益；
- 会话校验在每个请求都要做，必须能用**等值查询走主键索引** ——
  加盐会让"同一个令牌每次 hash 结果不同"，只能逐行比对，性能不可接受。

⚠️ 与用户密码的存储**完全不同**（密码必须慢 hash + 加盐）。这里存的是随机令牌。
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from aima_ugc.modules.identity.tables import identity_sessions_table
from aima_ugc.platform.time import beijing_now

# 浏览器 Cookie 名（登录接线单使用；放在这里避免"两处各写一个字面量"）。
SESSION_COOKIE_NAME = "aima_session"

# 随机令牌字节数：32 字节 = 256 位熵，暴力枚举不可行。
SESSION_TOKEN_BYTES = 32

# 会话有效期：8 小时（覆盖一个工作日），到期必须重新登录。
DEFAULT_SESSION_TTL = timedelta(hours=8)


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """一次会话查询的结果（**不含明文令牌**，也没有任何可反推令牌的字段）。"""

    principal_id: str
    display_name: str
    role: str
    avatar_url: str | None
    department_id: str | None
    department_name: str | None
    expires_at: datetime
    revoked_at: datetime | None
    last_seen_at: datetime

    def is_usable(self, *, now: datetime) -> bool:
        """判断会话此刻是否可用：未被撤销、且未过期。"""

        if self.revoked_at is not None:
            return False
        return now < self.expires_at


def hash_session_token(token: str) -> str:
    """把明文 Session Token 转成入库/查询用的 SHA-256 十六进制摘要。"""

    if not token:
        raise ValueError("session token 不能为空")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_session_token() -> str:
    """生成一枚高熵随机 Session Token（**只在内存/浏览器里存在，绝不落库**）。"""

    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


class SessionStore:
    """`identity_sessions` 的唯一写 Owner。"""

    def __init__(self, session: Session) -> None:
        """绑定调用方事务中的 PostgreSQL Session（本类不自己提交）。"""

        self._session = session

    def issue(
        self,
        *,
        principal_id: str,
        display_name: str,
        role: str,
        avatar_url: str | None = None,
        department_id: str | None = None,
        department_name: str | None = None,
        feishu_group_ids: Sequence[str] | None = None,
        ttl: timedelta = DEFAULT_SESSION_TTL,
    ) -> str:
        """新建会话并**返回明文令牌**（调用方立刻放进 HttpOnly Cookie）。

        返回的明文令牌是本方法唯一一次出现在内存中的机会 —— 它**不会**被写进数据库，
        也不会被写进日志。数据库里只有 `hash_session_token(令牌)`。

        `feishu_group_ids` 是**判角色时的依据留痕**：排查"这个人为什么是管理员"时，
        需要回看当时命中了哪几个飞书用户组。**它只用于审计，不参与任何授权判断**
        （授权只看 `role`），因此以逗号分隔文本落库、不建关系表。

        同期记录 `role_snapshot`：留下本次判定的角色快照，供后续角色变更审计对比。
        """

        if role not in {"administrator", "user"}:
            raise ValueError(f"role 只能是 administrator / user，收到 {role!r}")
        if ttl <= timedelta(0):
            raise ValueError("会话 ttl 必须大于 0")

        token = generate_session_token()
        now = beijing_now()
        # 组 ID 只作审计留痕：去重后按稳定顺序落库，避免同一批组因返回顺序不同产生无意义差异。
        groups_text = ",".join(sorted({g for g in (feishu_group_ids or ()) if g})) or None
        self._session.execute(
            identity_sessions_table.insert().values(
                token_hash=hash_session_token(token),
                principal_id=principal_id,
                display_name=display_name,
                avatar_url=avatar_url,
                role=role,
                department_id=department_id,
                department_name=department_name,
                feishu_group_ids=groups_text,
                role_snapshot=role,
                issued_at=now,
                expires_at=now + ttl,
                last_seen_at=now,
                revoked_at=None,
            )
        )
        return token

    def find(self, token: str) -> SessionRecord | None:
        """按**明文令牌**查会话；库内只做 hash 等值查询。"""

        row = (
            self._session.execute(
                select(
                    identity_sessions_table.c.principal_id,
                    identity_sessions_table.c.display_name,
                    identity_sessions_table.c.role,
                    identity_sessions_table.c.avatar_url,
                    identity_sessions_table.c.department_id,
                    identity_sessions_table.c.department_name,
                    identity_sessions_table.c.expires_at,
                    identity_sessions_table.c.revoked_at,
                    identity_sessions_table.c.last_seen_at,
                ).where(identity_sessions_table.c.token_hash == hash_session_token(token))
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return SessionRecord(
            principal_id=row["principal_id"],
            display_name=row["display_name"],
            role=row["role"],
            avatar_url=row["avatar_url"],
            department_id=row["department_id"],
            department_name=row["department_name"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            last_seen_at=row["last_seen_at"],
        )

    def touch_last_seen(self, token: str) -> None:
        """记录会话最近一次被使用的时间（用于"多久不用就过期"之类的治理）。"""

        self._session.execute(
            update(identity_sessions_table)
            .where(identity_sessions_table.c.token_hash == hash_session_token(token))
            .values(last_seen_at=beijing_now())
        )

    def revoke(self, token: str) -> bool:
        """撤销会话（登出）：**服务端失效**，不只是清浏览器 Cookie。

        返回本次是否真的撤销了一条可用会话（重复登出不报错、返回 `False`）。
        """

        result = cast(
            CursorResult[Any],
            self._session.execute(
                update(identity_sessions_table)
                .where(
                    identity_sessions_table.c.token_hash == hash_session_token(token),
                    identity_sessions_table.c.revoked_at.is_(None),
                )
                .values(revoked_at=beijing_now())
            ),
        )
        return bool(result.rowcount)

    def revoke_all_for_principal(self, principal_id: str) -> int:
        """撤销某个 Principal 的全部可用会话（例如管理员强制下线）。"""

        result = cast(
            CursorResult[Any],
            self._session.execute(
                update(identity_sessions_table)
                .where(
                    identity_sessions_table.c.principal_id == principal_id,
                    identity_sessions_table.c.revoked_at.is_(None),
                )
                .values(revoked_at=beijing_now())
            ),
        )
        return int(result.rowcount or 0)


__all__ = [
    "DEFAULT_SESSION_TTL",
    "SESSION_COOKIE_NAME",
    "SESSION_TOKEN_BYTES",
    "SessionRecord",
    "SessionStore",
    "generate_session_token",
    "hash_session_token",
]
