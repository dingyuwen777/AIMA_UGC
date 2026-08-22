"""关键词与词包 PostgreSQL Repository。"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.system.models import Keyword, KeywordPack, KeywordPackItem
from aima_ugc.modules.system.tables import (
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
)


@dataclass(frozen=True, slots=True)
class KeywordPackSummaryRecord:
    """配置页读取的词包摘要，不复制关键词明细。"""

    pack: KeywordPack
    keyword_count: int


def _pack_from_row(row: RowMapping) -> KeywordPack:
    return KeywordPack(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        enabled=row["enabled"],
        version=row["version"],
    )


def _keyword_from_row(row: RowMapping) -> Keyword:
    return Keyword(
        id=row["id"],
        text=row["text"],
        normalized_text=row["normalized_text"],
        enabled=row["enabled"],
    )


def _item_from_row(row: RowMapping) -> KeywordPackItem:
    return KeywordPackItem(
        pack_id=row["pack_id"],
        keyword_id=row["keyword_id"],
        platform_scope=row["platform_scope"],
        priority=row["priority"],
        enabled=row["enabled"],
        note=row["note"],
    )


class PostgresKeywordCatalogRepository:
    """System Owner 的关键词父事实 Repository；调用方拥有事务。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_pack(self, pack_id: UUID) -> KeywordPack | None:
        row = (
            self._session.execute(
                select(keyword_packs_table).where(keyword_packs_table.c.id == pack_id)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _pack_from_row(row)

    def get_pack_for_update(self, pack_id: UUID) -> KeywordPack | None:
        """锁定词包父记录，串行化启停、Relevance 与 Plan 保存。"""
        row = (
            self._session.execute(
                select(keyword_packs_table)
                .where(keyword_packs_table.c.id == pack_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _pack_from_row(row)

    def list_pack_summaries(
        self,
        *,
        search: str | None,
        enabled: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[KeywordPackSummaryRecord, ...]:
        """按更新时间稳定读取配置页摘要。"""
        conditions = []
        if search is not None:
            pattern = f"%{search.strip()}%"
            conditions.append(keyword_packs_table.c.name.ilike(pattern))
        if enabled is not None:
            conditions.append(keyword_packs_table.c.enabled.is_(enabled))
        rows = (
            self._session.execute(
                select(
                    *keyword_packs_table.c,
                    func.count(keyword_pack_items_table.c.keyword_id).label("keyword_count"),
                )
                .outerjoin(
                    keyword_pack_items_table,
                    keyword_pack_items_table.c.pack_id == keyword_packs_table.c.id,
                )
                .where(*conditions)
                .group_by(*keyword_packs_table.c)
                .order_by(keyword_packs_table.c.updated_at.desc(), keyword_packs_table.c.id)
                .offset(offset)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return tuple(
            KeywordPackSummaryRecord(
                pack=_pack_from_row(row),
                keyword_count=row["keyword_count"],
            )
            for row in rows
        )

    def count_packs(self, *, search: str | None, enabled: bool | None) -> int:
        conditions = []
        if search is not None:
            conditions.append(keyword_packs_table.c.name.ilike(f"%{search.strip()}%"))
        if enabled is not None:
            conditions.append(keyword_packs_table.c.enabled.is_(enabled))
        return int(
            self._session.scalar(
                select(func.count()).select_from(keyword_packs_table).where(*conditions)
            )
            or 0
        )

    def set_pack_enabled(self, pack_id: UUID, *, enabled: bool) -> KeywordPack | None:
        """切换词包状态并提升版本；无变化时保持版本稳定。"""
        current = self.get_pack_for_update(pack_id)
        if current is None:
            return None
        if current.enabled == enabled:
            return current
        row = (
            self._session.execute(
                update(keyword_packs_table)
                .where(keyword_packs_table.c.id == pack_id)
                .values(
                    enabled=enabled,
                    version=keyword_packs_table.c.version + 1,
                    updated_at=func.clock_timestamp(),
                )
                .returning(keyword_packs_table)
            )
            .mappings()
            .one()
        )
        return _pack_from_row(row)

    def create_pack(self, pack: KeywordPack) -> KeywordPack:
        now = func.clock_timestamp()
        row = (
            self._session.execute(
                insert(keyword_packs_table)
                .values(
                    id=pack.id,
                    name=pack.name,
                    description=pack.description,
                    enabled=pack.enabled,
                    version=pack.version,
                    created_at=now,
                    updated_at=now,
                )
                .returning(keyword_packs_table)
            )
            .mappings()
            .one()
        )
        return _pack_from_row(row)

    def get_keyword(self, keyword_id: UUID) -> Keyword | None:
        row = (
            self._session.execute(select(keywords_table).where(keywords_table.c.id == keyword_id))
            .mappings()
            .one_or_none()
        )
        return None if row is None else _keyword_from_row(row)

    def get_keyword_by_normalized_text(self, normalized_text: str) -> Keyword | None:
        row = (
            self._session.execute(
                select(keywords_table).where(keywords_table.c.normalized_text == normalized_text)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _keyword_from_row(row)

    def create_keyword(self, keyword: Keyword) -> Keyword:
        now = func.clock_timestamp()
        row = (
            self._session.execute(
                insert(keywords_table)
                .values(
                    id=keyword.id,
                    text=keyword.text,
                    normalized_text=keyword.normalized_text,
                    enabled=keyword.enabled,
                    created_at=now,
                    updated_at=now,
                )
                .returning(keywords_table)
            )
            .mappings()
            .one()
        )
        return _keyword_from_row(row)

    def get_or_create_keyword(self, keyword: Keyword) -> Keyword:
        now = func.clock_timestamp()
        row = (
            self._session.execute(
                pg_insert(keywords_table)
                .values(
                    id=keyword.id,
                    text=keyword.text,
                    normalized_text=keyword.normalized_text,
                    enabled=keyword.enabled,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=[keywords_table.c.normalized_text])
                .returning(keywords_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            return _keyword_from_row(row)
        existing = self.get_keyword_by_normalized_text(keyword.normalized_text)
        if existing is None:  # pragma: no cover - 唯一约束冲突后记录必然存在
            raise RuntimeError("关键词唯一冲突后无法读取既有记录")
        return existing

    def add_item(self, item: KeywordPackItem) -> KeywordPackItem:
        row = (
            self._session.execute(
                insert(keyword_pack_items_table)
                .values(
                    pack_id=item.pack_id,
                    keyword_id=item.keyword_id,
                    platform_scope=item.platform_scope,
                    priority=item.priority,
                    enabled=item.enabled,
                    note=item.note,
                )
                .returning(keyword_pack_items_table)
            )
            .mappings()
            .one()
        )
        updated_pack = self._session.execute(
            update(keyword_packs_table)
            .where(keyword_packs_table.c.id == item.pack_id)
            .values(
                version=keyword_packs_table.c.version + 1,
                updated_at=func.clock_timestamp(),
            )
            .returning(keyword_packs_table.c.id)
        ).scalar_one_or_none()
        if updated_pack != item.pack_id:
            raise RuntimeError(f"词包成员写入后无法提升版本: {item.pack_id}")
        return _item_from_row(row)

    def add_item_if_missing(self, item: KeywordPackItem) -> KeywordPackItem:
        row = (
            self._session.execute(
                pg_insert(keyword_pack_items_table)
                .values(
                    pack_id=item.pack_id,
                    keyword_id=item.keyword_id,
                    platform_scope=item.platform_scope,
                    priority=item.priority,
                    enabled=item.enabled,
                    note=item.note,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        keyword_pack_items_table.c.pack_id,
                        keyword_pack_items_table.c.keyword_id,
                        keyword_pack_items_table.c.platform_scope,
                    ]
                )
                .returning(keyword_pack_items_table)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            existing = (
                self._session.execute(
                    select(keyword_pack_items_table).where(
                        keyword_pack_items_table.c.pack_id == item.pack_id,
                        keyword_pack_items_table.c.keyword_id == item.keyword_id,
                        keyword_pack_items_table.c.platform_scope == item.platform_scope,
                    )
                )
                .mappings()
                .one()
            )
            return _item_from_row(existing)
        updated_pack = self._session.execute(
            update(keyword_packs_table)
            .where(keyword_packs_table.c.id == item.pack_id)
            .values(
                version=keyword_packs_table.c.version + 1,
                updated_at=func.clock_timestamp(),
            )
            .returning(keyword_packs_table.c.id)
        ).scalar_one_or_none()
        if updated_pack != item.pack_id:
            raise RuntimeError(f"词包成员写入后无法提升版本: {item.pack_id}")
        return _item_from_row(row)

    def list_keywords_for_pack(self, pack_id: UUID) -> list[tuple[Keyword, KeywordPackItem]]:
        rows = (
            self._session.execute(
                select(
                    keywords_table.c.id.label("keyword_id"),
                    keywords_table.c.text.label("keyword_text"),
                    keywords_table.c.normalized_text,
                    keywords_table.c.enabled.label("keyword_enabled"),
                    keyword_pack_items_table.c.platform_scope,
                    keyword_pack_items_table.c.priority,
                    keyword_pack_items_table.c.enabled.label("item_enabled"),
                    keyword_pack_items_table.c.note,
                )
                .join(
                    keyword_pack_items_table,
                    keyword_pack_items_table.c.keyword_id == keywords_table.c.id,
                )
                .where(keyword_pack_items_table.c.pack_id == pack_id)
                .order_by(
                    keyword_pack_items_table.c.priority,
                    keyword_pack_items_table.c.platform_scope,
                    keyword_pack_items_table.c.keyword_id,
                )
            )
            .mappings()
            .all()
        )
        return [
            (
                Keyword(
                    id=row["keyword_id"],
                    text=row["keyword_text"],
                    normalized_text=row["normalized_text"],
                    enabled=row["keyword_enabled"],
                ),
                KeywordPackItem(
                    pack_id=pack_id,
                    keyword_id=row["keyword_id"],
                    platform_scope=row["platform_scope"],
                    priority=row["priority"],
                    enabled=row["item_enabled"],
                    note=row["note"],
                ),
            )
            for row in rows
        ]

    def list_items(self, pack_id: UUID) -> list[KeywordPackItem]:
        rows = (
            self._session.execute(
                select(keyword_pack_items_table)
                .where(keyword_pack_items_table.c.pack_id == pack_id)
                .order_by(
                    keyword_pack_items_table.c.priority,
                    keyword_pack_items_table.c.platform_scope,
                    keyword_pack_items_table.c.keyword_id,
                )
            )
            .mappings()
            .all()
        )
        return [_item_from_row(row) for row in rows]
