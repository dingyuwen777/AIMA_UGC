"""词包成员修改必须保持共享 Keyword 的跨词包隔离。"""

from __future__ import annotations

from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.keyword_lifecycle import (
    PostgresKeywordPackLifecycleRepository,
)
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


def test_replacing_shared_keyword_only_changes_target_pack() -> None:
    """修改 Pack A 的共享关键词不能原地改坏仍引用旧词的 Pack B。"""

    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    pack_a = uuid4()
    pack_b = uuid4()
    old_keyword_id = uuid4()
    replacement_keyword_id = uuid4()
    try:
        with session.begin():
            catalog = PostgresKeywordCatalogRepository(session)
            for pack_id, name in ((pack_a, "共享关键词-A"), (pack_b, "共享关键词-B")):
                catalog.create_pack(
                    KeywordPack(
                        id=pack_id,
                        name=f"{name}-{pack_id}",
                        description="",
                        enabled=False,
                        version=1,
                    )
                )
            old_keyword = catalog.create_keyword(
                Keyword(
                    id=old_keyword_id,
                    text="共享关键词",
                    normalized_text="共享关键词",
                    enabled=True,
                )
            )
            replacement = catalog.create_keyword(
                Keyword(
                    id=replacement_keyword_id,
                    text="新的关键词",
                    normalized_text="新的关键词",
                    enabled=True,
                )
            )
            for pack_id in (pack_a, pack_b):
                catalog.add_item(
                    KeywordPackItem(
                        pack_id=pack_id,
                        keyword_id=old_keyword.id,
                        platform_scope="all",
                        priority=100,
                        enabled=True,
                        note="shared",
                    )
                )

            updated = PostgresKeywordPackLifecycleRepository(session).replace_item(
                pack_a,
                old_keyword.id,
                source_platform_scope="all",
                replacement_keyword_id=replacement.id,
                platform_scope="xiaohongshu",
                priority=50,
                enabled=False,
                note="updated",
                expected_version=2,
            )
            assert updated is not None
            assert updated.version == 3

            pack_a_keywords = catalog.list_keywords_for_pack(pack_a)
            pack_b_keywords = catalog.list_keywords_for_pack(pack_b)
            assert [
                (keyword.text, item.platform_scope, item.priority, item.enabled)
                for keyword, item in pack_a_keywords
            ] == [("新的关键词", "xiaohongshu", 50, False)]
            assert [(keyword.text, item.platform_scope) for keyword, item in pack_b_keywords] == [
                ("共享关键词", "all")
            ]
            assert catalog.get_keyword(old_keyword.id) is not None
    finally:
        with session.begin():
            session.execute(
                delete(keyword_pack_items_table).where(
                    keyword_pack_items_table.c.pack_id.in_((pack_a, pack_b))
                )
            )
            session.execute(
                delete(keyword_packs_table).where(keyword_packs_table.c.id.in_((pack_a, pack_b)))
            )
            session.execute(
                delete(keywords_table).where(
                    keywords_table.c.id.in_((old_keyword_id, replacement_keyword_id))
                )
            )
        session.close()
        runtime.dispose()
