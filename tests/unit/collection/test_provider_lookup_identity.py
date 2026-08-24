from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.adapters.providers.imports.identity import resolve_content_identity
from aima_ugc.adapters.providers.tikhub.runtime import build_comments_call, build_detail_call
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1


def _content(*, external_content_id: str, platform: str) -> CanonicalContentV1:
    observed_at = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    return CanonicalContentV1(
        platform=platform,  # type: ignore[arg-type]
        external_content_id=external_content_id,
        content_type="video",
        observed_at=observed_at,
        source=CanonicalSourceV1(
            provider_name="imports",
            provider_request_id=str(uuid4()),
            provider_attempt_id=str(uuid4()),
            raw_artifact_id=uuid4(),
            source_type="aima-monitoring-excel.v1",
            source_value="source.xlsx",
            item_locator="sheet=文章;row=2",
            observed_at=observed_at,
        ),
        observed_fields=["content_type"],
    )


def test_excel_standard_urls_record_typed_provider_lookup_ids() -> None:
    cases = (
        (
            "xiaohongshu",
            "https://www.xiaohongshu.com/explore/6a81d4300000000028002076",
            "6a81d4300000000028002076",
            "note_id",
        ),
        (
            "douyin",
            "https://www.douyin.com/video/7298145681699622182",
            "7298145681699622182",
            "aweme_id",
        ),
        (
            "kuaishou",
            "https://www.kuaishou.com/short-video/3xabc123",
            "3xabc123",
            "photo_id",
        ),
        (
            "weibo",
            "https://weibo.com/detail/5191839277071122",
            "5191839277071122",
            "status_id",
        ),
    )
    for platform, url, expected_id, id_type in cases:
        identity = resolve_content_identity(
            platform=platform,
            canonical_url=url,
            source_article_id=None,
        )
        assert identity.external_content_id == expected_id
        assert identity.alternate_ids[id_type] == expected_id


@pytest.mark.parametrize(
    ("platform", "url", "article_id", "id_type", "expected_id"),
    (
        (
            "xiaohongshu",
            "https://www.xiaohongshu.com/explore/6a85c701000000001d0040e2",
            "5e1968f135ce44ad838f650d3205d94d",
            "note_id",
            "6a85c701000000001d0040e2",
        ),
        (
            "douyin",
            "https://www.douyin.com/share/video/7675702103746898533",
            "4bbf18abf1abf7cd39f58ff5d1ce5d27",
            "aweme_id",
            "7675702103746898533",
        ),
        (
            "douyin",
            "https://www.iesdouyin.com/share/video/7675628205508711089",
            "b48827a69fd4278dcb325ad6c50b7c57",
            "aweme_id",
            "7675628205508711089",
        ),
        (
            "weibo",
            "http://weibo.com/1914372032/Re8y6x01w",
            "579408948a641a0bbc2b7f72bb60d6f5",
            "status_id",
            "5333694587864918",
        ),
        (
            "bilibili",
            "https://www.bilibili.com/video/av117119547215182/",
            "a7a649d6e3ca41356ca972ec3f657542",
            "av_id",
            "117119547215182",
        ),
        (
            "kuaishou",
            "https://www.kuaishou.com/short-video/3x8hhinajs8pgpq",
            "50bbb81bac5bfb3bb3de84c2e4c1c169",
            "photo_id",
            "3x8hhinajs8pgpq",
        ),
        (
            "kuaishou",
            "https://live.kuaishou.com/u/3xsvp556vkpta2e/3xkfnk9freeuzuc",
            "cf624299f76ad8e562474703b9b74b7b",
            "photo_id",
            "3xkfnk9freeuzuc",
        ),
    ),
)
def test_uploaded_excel_urls_prefer_native_lookup_over_source_article_id(
    platform: str,
    url: str,
    article_id: str,
    id_type: str,
    expected_id: str,
) -> None:
    identity = resolve_content_identity(
        platform=platform,
        canonical_url=url,
        source_article_id=article_id,
    )

    assert identity.external_content_id == expected_id
    assert identity.alternate_ids[id_type] == expected_id
    assert identity.alternate_ids["source_article_id"] == article_id


def test_excel_douyin_modal_id_is_typed_aweme_lookup() -> None:
    identity = resolve_content_identity(
        platform="douyin",
        canonical_url=(
            "https://www.douyin.com/search/%E7%88%B1%E7%8E%9B?"
            "modal_id=7531234567890123456&type=video"
        ),
        source_article_id=None,
    )

    assert identity.external_content_id == "7531234567890123456"
    assert identity.alternate_ids["aweme_id"] == "7531234567890123456"


def test_excel_bilibili_urls_normalize_bv_to_tikhub_aid_and_keep_lookup_aliases() -> None:
    bv = resolve_content_identity(
        platform="bilibili",
        canonical_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_article_id=None,
    )
    av = resolve_content_identity(
        platform="bilibili",
        canonical_url="https://www.bilibili.com/video/av170001",
        source_article_id=None,
    )

    assert bv.external_content_id == "2"
    assert bv.alternate_ids["av_id"] == "2"
    assert bv.alternate_ids["bv_id"] == "BV1xx411c7mD"
    assert av.external_content_id == "170001"
    assert av.alternate_ids["av_id"] == "170001"


def test_excel_weibo_permalink_converts_base62_bid_to_numeric_status_id() -> None:
    identity = resolve_content_identity(
        platform="weibo",
        canonical_url="https://weibo.com/2034565060/Hd1N2qpta",
        source_article_id=None,
    )

    assert identity.external_content_id == "4331051486294436"
    assert identity.alternate_ids["status_id"] == "4331051486294436"


def test_bilibili_runtime_routes_bv_identity_to_bv_parameter() -> None:
    content = _content(external_content_id="BV1xx411c7mD", platform="bilibili")

    detail = build_detail_call("bilibili", content)
    comments = build_comments_call(
        platform="bilibili",
        external_content_id=content.external_content_id,
    )

    assert detail.params["bv_id"] == "BV1xx411c7mD"
    assert "av_id" not in detail.params
    assert comments.params["bv_id"] == "BV1xx411c7mD"
    assert "av_id" not in comments.params


def test_bilibili_runtime_normalizes_legacy_av_prefix_before_provider_call() -> None:
    content = _content(external_content_id="av170001", platform="bilibili")

    detail = build_detail_call("bilibili", content)
    comments = build_comments_call(platform="bilibili", external_content_id="av170001")

    assert detail.params["av_id"] == "170001"
    assert comments.params["av_id"] == "170001"
