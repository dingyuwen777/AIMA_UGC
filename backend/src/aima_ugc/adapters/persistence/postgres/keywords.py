"""关键词与词包 PostgreSQL Repository。"""

from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.system.models import Keyword, KeywordPack, KeywordPackItem
from aima_ugc.modules.system.tables import (
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
)


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
        platform=row["platform"],
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

    def add_item(self, item: KeywordPackItem) -> KeywordPackItem:
        row = (
            self._session.execute(
                insert(keyword_pack_items_table)
                .values(
                    pack_id=item.pack_id,
                    keyword_id=item.keyword_id,
                    platform=item.platform,
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

    def list_items(self, pack_id: UUID) -> list[KeywordPackItem]:
        rows = (
            self._session.execute(
                select(keyword_pack_items_table)
                .where(keyword_pack_items_table.c.pack_id == pack_id)
                .order_by(
                    keyword_pack_items_table.c.priority,
                    keyword_pack_items_table.c.platform,
                    keyword_pack_items_table.c.keyword_id,
                )
            )
            .mappings()
            .all()
        )
        return [_item_from_row(row) for row in rows]
