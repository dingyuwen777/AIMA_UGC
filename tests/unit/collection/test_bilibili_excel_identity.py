from aima_ugc.adapters.providers.imports.identity import resolve_content_identity


def test_bilibili_bv_url_normalizes_to_same_numeric_aid_used_by_tikhub() -> None:
    identity = resolve_content_identity(
        platform="bilibili",
        canonical_url="https://www.bilibili.com/video/BV17x411w7KC/",
        source_article_id="SOURCE-BILI",
    )

    assert identity.external_content_id == "170001"
    assert identity.alternate_ids == {
        "bvid": "BV17x411w7KC",
        "bv_id": "BV17x411w7KC",
        "av_id": "170001",
        "source_article_id": "SOURCE-BILI",
    }


def test_bilibili_small_aid_bv_pair_keeps_numeric_primary_identity() -> None:
    identity = resolve_content_identity(
        platform="bilibili",
        canonical_url="https://www.bilibili.com/video/BV1xx411c7mD/",
        source_article_id=None,
    )

    assert identity.external_content_id == "2"
    assert identity.alternate_ids["av_id"] == "2"
    assert identity.alternate_ids["bv_id"] == "BV1xx411c7mD"
