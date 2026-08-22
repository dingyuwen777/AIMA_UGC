"""Stage 7 关键词与词包 PostgreSQL Repository 集成测试。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.modules.system.models import Keyword, KeywordPack, KeywordPackItem
from aima_ugc.modules.system.tables import (
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError


def test_keyword_catalog_round_trip_and_database_constraints() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    pack_id = uuid4()
    keyword_id = uuid4()
    pack = KeywordPack(
        id=pack_id,
        name=f"爱玛品牌词-{pack_id}",
        description="品牌核心词包",
        enabled=True,
        version=1,
    )
    keyword = Keyword(
        id=keyword_id,
        text="爱玛",
        normalized_text=f"爱玛-{keyword_id}",
        enabled=True,
    )
    item = KeywordPackItem(
        pack_id=pack_id,
        keyword_id=keyword_id,
        platform_scope="all",
        priority=10,
        enabled=True,
        note="默认全平台品牌词",
    )

    try:
        repository = PostgresKeywordCatalogRepository(session)
        with session.begin():
            created_pack = repository.create_pack(pack)
            created_keyword = repository.create_keyword(keyword)
            created_item = repository.add_item(item)

        with session.begin():
            loaded_pack = repository.get_pack(pack_id)
            loaded_keyword = repository.get_keyword(keyword_id)
            loaded_by_normalized = repository.get_keyword_by_normalized_text(
                keyword.normalized_text
            )
            loaded_items = repository.list_items(pack_id)

        assert created_pack == pack
        assert loaded_pack is not None
        assert loaded_pack.version == 2
        assert loaded_pack.name == pack.name
        assert loaded_pack.description == pack.description
        assert loaded_pack.enabled == pack.enabled
        assert created_keyword == loaded_keyword == loaded_by_normalized == keyword
        assert created_item == item
        assert loaded_items == [item]

        duplicate_keyword = Keyword(
            id=uuid4(),
            text="同一规范化身份的另一种原文",
            normalized_text=keyword.normalized_text,
            enabled=True,
        )
        with pytest.raises(IntegrityError):
            with session.begin():
                repository.create_keyword(duplicate_keyword)

        with pytest.raises(IntegrityError):
            with session.begin():
                repository.add_item(item)

        missing_pack_item = KeywordPackItem(
            pack_id=uuid4(),
            keyword_id=keyword_id,
            platform_scope="xiaohongshu",
            priority=20,
            enabled=True,
            note="用于验证外键",
        )
        with pytest.raises(IntegrityError):
            with session.begin():
                repository.add_item(missing_pack_item)

        assert keyword_packs_table.info["owner"] == "system"
        assert keywords_table.info["owner"] == "system"
        assert keyword_pack_items_table.info["owner"] == "system"
        assert set(keyword_pack_items_table.c.keys()) == {
            "pack_id",
            "keyword_id",
            "platform_scope",
            "priority",
            "enabled",
            "note",
        }
        assert tuple(column.name for column in keyword_pack_items_table.primary_key.columns) == (
            "pack_id",
            "keyword_id",
            "platform_scope",
        )
        assert {
            foreign_key.target_fullname for foreign_key in keyword_pack_items_table.foreign_keys
        } == {
            "keyword_packs.id",
            "keywords.id",
        }
    finally:
        session.close()
        with runtime.engine.begin() as connection:
            connection.execute(
                delete(keyword_pack_items_table).where(
                    keyword_pack_items_table.c.pack_id == pack_id
                )
            )
            connection.execute(
                delete(keyword_packs_table).where(keyword_packs_table.c.id == pack_id)
            )
            connection.execute(delete(keywords_table).where(keywords_table.c.id == keyword_id))
        runtime.dispose()
