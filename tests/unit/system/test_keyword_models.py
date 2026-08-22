"""Stage 7 关键词与词包稳定业务对象测试。"""

from uuid import uuid4

from aima_ugc.modules.system.models import Keyword, KeywordPack, KeywordPackItem


def test_keyword_catalog_models_keep_explicit_identity_and_item_metadata() -> None:
    pack_id = uuid4()
    keyword_id = uuid4()
    pack = KeywordPack(
        id=pack_id,
        name="爱玛品牌词",
        description="品牌核心词包",
        enabled=True,
        version=1,
    )
    keyword = Keyword(
        id=keyword_id,
        text="ＡＩＭＡ",
        normalized_text="aima",
        enabled=True,
    )
    item = KeywordPackItem(
        pack_id=pack_id,
        keyword_id=keyword_id,
        platform_scope="all",
        priority=10,
        enabled=True,
        note="品牌英文全角写法",
    )

    assert pack.name == "爱玛品牌词"
    assert pack.version == 1
    assert keyword.text == "ＡＩＭＡ"
    assert keyword.normalized_text == "aima"
    assert item.platform_scope == "all"
    assert item.priority == 10
    assert item.note == "品牌英文全角写法"
