"""全局 Relevance 配置与冻结快照的 System Owner PostgreSQL 入口。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from aima_ugc.contracts.analysis import RelevanceSnapshotV1
from aima_ugc.modules.analysis import RelevanceKeyword, RelevanceService
from aima_ugc.modules.system.models import GlobalRelevanceConfig
from aima_ugc.modules.system.tables import (
    global_relevance_config_table,
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
)


class GlobalRelevanceUnavailable(RuntimeError):
    """配置缺失、Pack 停用或没有有效关键词时 fail closed。"""


class PostgresGlobalRelevanceRepository:
    """配置写入和一次 statement 快照读取；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def set(self, keyword_pack_id: UUID) -> GlobalRelevanceConfig:
        pack_exists = self._session.scalar(
            select(keyword_packs_table.c.id).where(keyword_packs_table.c.id == keyword_pack_id)
        )
        if pack_exists is None:
            raise LookupError("Keyword Pack 不存在")
        now = func.clock_timestamp()
        row = (
            self._session.execute(
                pg_insert(global_relevance_config_table)
                .values(
                    singleton_key="global",
                    keyword_pack_id=keyword_pack_id,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[global_relevance_config_table.c.singleton_key],
                    set_={
                        "keyword_pack_id": keyword_pack_id,
                        "version": global_relevance_config_table.c.version + 1,
                        "updated_at": now,
                    },
                )
                .returning(*global_relevance_config_table.c)
            )
            .mappings()
            .one()
        )
        return GlobalRelevanceConfig(
            keyword_pack_id=row["keyword_pack_id"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get(self) -> GlobalRelevanceConfig | None:
        row = self._session.execute(select(global_relevance_config_table)).mappings().one_or_none()
        if row is None:
            return None
        return GlobalRelevanceConfig(
            keyword_pack_id=row["keyword_pack_id"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def snapshot(self) -> tuple[RelevanceSnapshotV1, datetime]:
        rows = (
            self._session.execute(
                select(
                    global_relevance_config_table.c.version.label("config_version"),
                    global_relevance_config_table.c.updated_at,
                    keyword_packs_table.c.id.label("pack_id"),
                    keyword_packs_table.c.version.label("pack_version"),
                    keyword_packs_table.c.enabled.label("pack_enabled"),
                    keyword_pack_items_table.c.priority,
                    keyword_pack_items_table.c.enabled.label("item_enabled"),
                    keywords_table.c.id.label("keyword_id"),
                    keywords_table.c.text.label("keyword_text"),
                    keywords_table.c.enabled.label("keyword_enabled"),
                )
                .select_from(
                    global_relevance_config_table.join(
                        keyword_packs_table,
                        global_relevance_config_table.c.keyword_pack_id == keyword_packs_table.c.id,
                    )
                    .outerjoin(
                        keyword_pack_items_table,
                        keyword_pack_items_table.c.pack_id == keyword_packs_table.c.id,
                    )
                    .outerjoin(
                        keywords_table,
                        keywords_table.c.id == keyword_pack_items_table.c.keyword_id,
                    )
                )
                .where(global_relevance_config_table.c.singleton_key == "global")
                .order_by(
                    keyword_pack_items_table.c.priority,
                    keyword_pack_items_table.c.platform,
                    keyword_pack_items_table.c.keyword_id,
                )
            )
            .mappings()
            .all()
        )
        if not rows or not rows[0]["pack_enabled"]:
            raise GlobalRelevanceUnavailable("全局 Relevance 配置缺失或词包已停用")
        configured = tuple(
            RelevanceKeyword(text=row["keyword_text"], priority=row["priority"])
            for row in rows
            if row["keyword_id"] is not None and row["item_enabled"] and row["keyword_enabled"]
        )
        try:
            relevance = RelevanceService(configured)
        except ValueError as exc:
            raise GlobalRelevanceUnavailable("全局 Relevance 词包没有有效关键词") from exc
        first = rows[0]
        snapshot = RelevanceSnapshotV1(
            keyword_pack_id=first["pack_id"],
            keyword_pack_version=first["pack_version"],
            config_version=first["config_version"],
            effective_keywords=relevance.effective_keywords,
        )
        return snapshot, first["updated_at"]


__all__ = [
    "GlobalRelevanceUnavailable",
    "PostgresGlobalRelevanceRepository",
]
