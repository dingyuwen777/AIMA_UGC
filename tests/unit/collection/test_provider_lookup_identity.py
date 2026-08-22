from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

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


def test_excel_bilibili_urls_preserve_av_bv_lookup_type() -> None:
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

    assert bv.external_content_id == "BV1xx411c7mD"
    assert bv.alternate_ids["bv_id"] == "BV1xx411c7mD"
    assert av.external_content_id == "170001"
    assert av.alternate_ids["av_id"] == "170001"


def test_excel_ambiguous_weibo_permalink_is_not_marked_as_status_lookup() -> None:
    identity = resolve_content_identity(
        platform="weibo",
        canonical_url="https://weibo.com/1234567890/PabcdEF12",
        source_article_id=None,
    )

    assert identity.external_content_id == "PabcdEF12"
    assert "status_id" not in identity.alternate_ids


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
