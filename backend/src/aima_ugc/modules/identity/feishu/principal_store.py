"""外部身份 → AIMA Principal 的映射读写。

════════ 这里是"映射"真正发生的地方 ════════

本模块只做一件事：把外部身份标识（飞书的 `union_id` / `open_id`）**换成一个 AIMA 自己
的 `principal_id`（Uuid）**，并保证同一身份永远换到同一个值。

    按 (connector_id, provider_subject) 查 identity_external_identities
        命中 → 复用它的 principal_id（**不新建**）
        未命中 → 新建 identity_principals + 写入映射

════════ 为什么"查不到就新建"必须防并发 ════════

两个人几乎同时首次登录（或同一个人开了两个页面同时回调）时，
"A 查询→没查到→插入"与"B 查询→没查到→插入"会**各自建一个 Principal**。
数据库里的 `UNIQUE(connector_id, provider_subject)` 会让后插入的那条报错，
但前一条已经落库 → 表面上"登录失败"，实际上已经把同一个人拆成了两个身份。

正确做法：把"新建 Principal + 写映射"这两步放进一个 **SAVEPOINT（保存点）**。
冲突时只回滚这个保存点 —— 刚建的 Principal 和被拒的映射一起消失（不留孤儿行），
而调用方事务里更早的写入（例如审计）**不受影响**；然后回头重读赢家的 `principal_id`。
这样并发下也只有一个 Principal 被复用，且不会把异常抛给调用方。

⚠️ 不能用"捕获 `IntegrityError` 后 `session.rollback()`"来替代：那会连同调用方
本事务更早的写入一起丢掉。SAVEPOINT 回滚的范围恰好只覆盖本次新建。

════════ 与飞书私有字段的边界 ════════

本模块的入参 `provider_subject` 是**Provider 中立的业务参数名**，不是飞书字段名：
调用方（后续接线单）负责把 `union_id`（优先）或 `open_id` 归一成它。
本模块**不 import 任何飞书类型**，也不解析飞书响应。
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aima_ugc.modules.identity.tables import (
    identity_external_identities_table,
    identity_principals_table,
)
from aima_ugc.platform.time import beijing_now


@dataclass(frozen=True, slots=True)
class ResolvedPrincipal:
    """一次身份解析的结果：AIMA 稳定 ID + 展示名 + 本次是否新建。"""

    principal_id: str
    display_name: str
    # `created` 供登录流程写审计日志用（区分"新用户首次登录"与"老用户登录"）。
    created: bool


class PrincipalStore:
    """`identity_principals` / `identity_external_identities` 的唯一写 Owner。"""

    def __init__(self, session: Session) -> None:
        """绑定调用方事务中的 PostgreSQL Session（本类不自己提交）。"""

        self._session = session

    def find_principal_id(self, *, connector_id: str, provider_subject: str) -> str | None:
        """按 `(connector_id, provider_subject)` 查已有映射；没有则返回 `None`。"""

        return self._session.scalar(
            select(identity_external_identities_table.c.principal_id).where(
                identity_external_identities_table.c.connector_id == connector_id,
                identity_external_identities_table.c.provider_subject == provider_subject,
            )
        )

    def resolve_or_create(
        self,
        *,
        connector_id: str,
        provider: str,
        provider_subject: str,
        display_name: str,
    ) -> ResolvedPrincipal:
        """按外部身份取得 AIMA Principal；**同一身份重复调用不会新建**。

        `display_name` 只在**首次创建**时写入；已有 Principal 不会被外部身份
        静默改名（改名属于用户资料，不是登录流程的职责，避免外部侧改名字污染 AIMA）。
        """

        if not provider or provider != provider.strip():
            raise ValueError("provider 必须是非空且已清洗的字符串")
        if not provider_subject or provider_subject != provider_subject.strip():
            raise ValueError("provider_subject 必须是非空且已清洗的字符串")
        if not display_name or display_name != display_name.strip():
            raise ValueError("display_name 必须是非空且已清洗的字符串")

        existing = self.find_principal_id(
            connector_id=connector_id, provider_subject=provider_subject
        )
        if existing is not None:
            return ResolvedPrincipal(
                principal_id=existing,
                display_name=self._display_name_of(existing),
                created=False,
            )

        return self._create_mapping(
            connector_id=connector_id,
            provider=provider,
            provider_subject=provider_subject,
            display_name=display_name,
        )

    def touch_last_seen(self, *, connector_id: str, provider_subject: str) -> None:
        """记录"这个外部身份最近一次登录时间"，供活跃度统计与排障使用。"""

        now = beijing_now()
        self._session.execute(
            update(identity_external_identities_table)
            .where(
                identity_external_identities_table.c.connector_id == connector_id,
                identity_external_identities_table.c.provider_subject == provider_subject,
            )
            .values(last_seen_at=now, updated_at=now)
        )

    # ------------------------------------------------------------------ 内部
    def _display_name_of(self, principal_id: str) -> str:
        """读已有 Principal 的展示名。"""

        name = self._session.scalar(
            select(identity_principals_table.c.display_name).where(
                identity_principals_table.c.id == principal_id
            )
        )
        # 理论上不会发生（有外键）；真发生了说明数据被绕过外键破坏，如实暴露而不是编名字。
        if name is None:
            raise LookupError(f"principal_id={principal_id} 没有对应的 identity_principals 行")
        return str(name)

    def _create_mapping(
        self,
        *,
        connector_id: str,
        provider: str,
        provider_subject: str,
        display_name: str,
    ) -> ResolvedPrincipal:
        """新建 Principal 并写映射；**并发冲突时回退为复用赢家，不抛异常**。"""

        now = beijing_now()
        principal_id = uuid4().hex
        try:
            with self._session.begin_nested():
                self._session.execute(
                    insert(identity_principals_table).values(
                        id=principal_id,
                        display_name=display_name,
                        created_at=now,
                        updated_at=now,
                        last_seen_at=now,
                    )
                )
                self._session.execute(
                    insert(identity_external_identities_table).values(
                        id=uuid4().hex,
                        principal_id=principal_id,
                        connector_id=connector_id,
                        provider=provider,
                        provider_subject=provider_subject,
                        created_at=now,
                        updated_at=now,
                        last_seen_at=now,
                    )
                )
        except IntegrityError:
            # 并发中"我"输了：另一个事务先写了同一个 (connector_id, provider_subject)。
            # 保存点已把刚建的 Principal 与映射一起回滚（不留孤儿行），这里复用赢家。
            winner = self.find_principal_id(
                connector_id=connector_id, provider_subject=provider_subject
            )
            if winner is None:
                # 冲突却读不到赢家 —— 不是并发，而是别的完整性错误（例如外键）。
                # 绝不能静默吞掉，否则会掩盖真实的 Schema/数据问题。
                raise
            return ResolvedPrincipal(
                principal_id=winner,
                display_name=self._display_name_of(winner),
                created=False,
            )
        return ResolvedPrincipal(
            principal_id=principal_id,
            display_name=display_name,
            created=True,
        )


__all__ = ["PrincipalStore", "ResolvedPrincipal"]
