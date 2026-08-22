"""Scheduled Run 创建时的一次性关键词快照读取器。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.scheduled_scopes import (
    ScheduledKeywordEntry,
    ScheduledKeywordPackSnapshot,
)
from aima_ugc.modules.system.tables import (
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
)


class MissingScheduledKeywordPackError(RuntimeError):
    """Plan 引用的词包无法在同一次数据库快照中读取。"""


@dataclass(frozen=True, slots=True)
class ScheduledKeywordCatalogSnapshot:
    """单条 SQL statement 得到的词包版本和关联关键词事实。"""

    keyword_packs: tuple[ScheduledKeywordPackSnapshot, ...]
    entries: tuple[ScheduledKeywordEntry, ...]


class PostgresScheduledKeywordSnapshotReader:
    """只读 System 词包表，在一个 statement snapshot 内冻结 Run 输入。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def read(self, pack_ids: tuple[UUID, ...]) -> ScheduledKeywordCatalogSnapshot:
        if not pack_ids:
            return ScheduledKeywordCatalogSnapshot(keyword_packs=(), entries=())
        requested = set(pack_ids)
        if len(requested) != len(pack_ids):
            raise ValueError("scheduled keyword pack ids 不得重复")

        rows = (
            self._session.execute(
                select(
                    keyword_packs_table.c.id.label("pack_id"),
                    keyword_packs_table.c.version.label("pack_version"),
                    keyword_packs_table.c.enabled.label("pack_enabled"),
                    keyword_pack_items_table.c.keyword_id,
                    keyword_pack_items_table.c.platform_scope.label("item_platform_scope"),
                    keyword_pack_items_table.c.priority,
                    keyword_pack_items_table.c.enabled.label("item_enabled"),
                    keywords_table.c.text.label("keyword_text"),
                    keywords_table.c.normalized_text.label("keyword_normalized_text"),
                    keywords_table.c.enabled.label("keyword_enabled"),
                )
                .select_from(
                    keyword_packs_table.outerjoin(
                        keyword_pack_items_table,
                        keyword_pack_items_table.c.pack_id == keyword_packs_table.c.id,
                    ).outerjoin(
                        keywords_table,
                        keywords_table.c.id == keyword_pack_items_table.c.keyword_id,
                    )
                )
                .where(keyword_packs_table.c.id.in_(pack_ids))
                .order_by(
                    keyword_packs_table.c.id,
                    keyword_pack_items_table.c.priority,
                    keyword_pack_items_table.c.platform_scope,
                    keyword_pack_items_table.c.keyword_id,
                )
            )
            .mappings()
            .all()
        )

        packs_by_id: dict[UUID, ScheduledKeywordPackSnapshot] = {}
        entries: list[ScheduledKeywordEntry] = []
        for row in rows:
            pack_id = row["pack_id"]
            pack = ScheduledKeywordPackSnapshot(
                pack_id=pack_id,
                version=row["pack_version"],
                enabled=row["pack_enabled"],
            )
            packs_by_id[pack_id] = pack
            keyword_id = row["keyword_id"]
            if keyword_id is None:
                continue
            entries.append(
                ScheduledKeywordEntry(
                    pack_id=pack_id,
                    pack_version=pack.version,
                    pack_enabled=pack.enabled,
                    keyword_id=keyword_id,
                    keyword_text=row["keyword_text"],
                    keyword_normalized_text=row["keyword_normalized_text"],
                    keyword_enabled=row["keyword_enabled"],
                    item_platform_scope=row["item_platform_scope"],
                    priority=row["priority"],
                    item_enabled=row["item_enabled"],
                )
            )

        missing = requested - set(packs_by_id)
        if missing:
            missing_text = ", ".join(sorted(str(item) for item in missing))
            raise MissingScheduledKeywordPackError(
                f"scheduled run 无法读取 Plan 引用词包: {missing_text}"
            )

        return ScheduledKeywordCatalogSnapshot(
            keyword_packs=tuple(sorted(packs_by_id.values(), key=lambda item: str(item.pack_id))),
            entries=tuple(entries),
        )


__all__ = [
    "MissingScheduledKeywordPackError",
    "PostgresScheduledKeywordSnapshotReader",
    "ScheduledKeywordCatalogSnapshot",
]
