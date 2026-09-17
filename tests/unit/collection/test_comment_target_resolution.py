"""五平台评论目标必须来自明确的 Provider 身份。"""

from __future__ import annotations

import pytest
from aima_ugc.adapters.persistence.postgres.collection_targets import _lookup_identity
from aima_ugc.adapters.providers.tikhub.runtime import (
    build_comments_call,
    build_identity_resolution_call,
    build_sub_comments_call,
)
from aima_ugc.modules.collection.comment_target import (
    identity_block_reason,
    resolve_supported_locator,
)


@pytest.mark.parametrize(
    ("platform", "id_type", "url", "path", "parameter"),
    (
        (
            "xiaohongshu",
            "share_text",
            "https://xhslink.com/o/8fCmVEVQWmp",
            "/api/v1/xiaohongshu/app_v2/get_image_note_detail",
            "share_text",
        ),
        (
            "douyin",
            "douyin_share_url",
            "https://v.douyin.com/e3x2fjE/",
            "/api/v1/douyin/app/v3/fetch_one_video_by_share_url",
            "share_url",
        ),
    ),
)
def test_verified_share_locator_uses_separate_detail_operation(
    platform: str, id_type: str, url: str, path: str, parameter: str
) -> None:
    locator = resolve_supported_locator(platform, {id_type: url})
    assert locator == (id_type, url)
    call = build_identity_resolution_call(platform=platform, locator_type=id_type, locator=url)
    assert call.path == path
    assert call.params == {parameter: url}
    assert call.business_operation == "identity_resolution"


@pytest.mark.parametrize(
    ("platform", "id_type", "url"),
    (
        ("xiaohongshu", "share_text", "https://xhslink.com.evil.invalid/o/abc"),
        ("xiaohongshu", "share_text", "https://user@xhslink.com/o/abc"),
        ("douyin", "douyin_share_url", "http://127.0.0.1/abc"),
        ("douyin", "douyin_share_url", "https://v.douyin.com.evil.invalid/abc"),
    ),
)
def test_share_locator_rejects_unapproved_origin(platform: str, id_type: str, url: str) -> None:
    assert resolve_supported_locator(platform, {id_type: url}) is None
    with pytest.raises(ValueError, match="identity_unavailable"):
        build_identity_resolution_call(platform=platform, locator_type=id_type, locator=url)


@pytest.mark.parametrize(
    ("platform", "external_content_id", "alternate_ids"),
    (
        ("xiaohongshu", "url_sha256:abc", {"share_text": "https://xhslink.com/abc"}),
        ("douyin", "SOURCE-001", {"douyin_share_url": "https://v.douyin.com/abc"}),
        ("weibo", "230940123456789", {}),
        ("bilibili", "SOURCE-001", {"bilibili_share_url": "https://b23.tv/abc"}),
        ("kuaishou", "SOURCE-001", {"kuaishou_share_url": "https://v.kuaishou.com/abc"}),
    ),
)
def test_unresolved_content_never_builds_comment_request(
    platform: str, external_content_id: str, alternate_ids: dict[str, str]
) -> None:
    """定位身份和 Canonical 主身份均不能冒充评论目标。"""
    with pytest.raises(ValueError, match="identity_unavailable"):
        build_comments_call(
            platform=platform,  # type: ignore[arg-type]
            external_content_id=external_content_id,
            alternate_ids=alternate_ids,
        )
    with pytest.raises(ValueError, match="identity_unavailable"):
        build_sub_comments_call(
            platform=platform,  # type: ignore[arg-type]
            external_content_id=external_content_id,
            alternate_ids=alternate_ids,
            root_comment_id="root-1",
        )


@pytest.mark.parametrize(
    ("platform", "id_type", "value", "parameter"),
    (
        ("xiaohongshu", "note_id", "6a81d4300000000028002076", "note_id"),
        ("douyin", "aweme_id", "7298145681699622182", "aweme_id"),
        ("weibo", "status_id", "5191839277071122", "status_id"),
        ("bilibili", "av_id", "170001", "av_id"),
        ("kuaishou", "photo_id", "3x8hhinajs8pgpq", "photo_id"),
    ),
)
def test_typed_comment_target_routes_to_expected_provider_parameter(
    platform: str, id_type: str, value: str, parameter: str
) -> None:
    """五平台已确认的 typed ID 仍可进入正式评论接口。"""
    call = build_comments_call(
        platform=platform,  # type: ignore[arg-type]
        external_content_id="SOURCE-001",
        alternate_ids={id_type: value},
    )
    assert call.params[parameter] == value


def test_platform_mismatched_typed_id_is_rejected() -> None:
    """其他平台的 ID 类型不能借 Canonical 字段绕过校验。"""
    with pytest.raises(ValueError, match="identity_unavailable"):
        build_comments_call(
            platform="douyin",
            external_content_id="7298145681699622182",
            alternate_ids={"status_id": "7298145681699622182"},
        )


def test_legacy_ttarticle_locator_blocks_even_with_status_id() -> None:
    """旧数据带文章定位字段时也不能请求帖子评论。"""
    with pytest.raises(ValueError, match="identity_unavailable"):
        build_comments_call(
            platform="weibo",
            external_content_id="SOURCE-001",
            alternate_ids={"ttarticle_id": "230940123456789", "status_id": "5191839277071122"},
        )

    assert (
        _lookup_identity(
            platform="weibo",
            external_content_id="5191839277071122",
            alternate_ids={
                "ttarticle_id": "230940123456789",
                "status_id": "5191839277071122",
            },
            has_tikhub_source=True,
        )
        is None
    )
    assert (
        identity_block_reason(
            "weibo",
            {
                "ttarticle_id": "230940123456789",
                "weibo_video_url": "https://weibo.com/tv/show/123",
            },
        )
        == "identity_unavailable"
    )
    with pytest.raises(ValueError, match="identity_unavailable"):
        build_comments_call(
            platform="weibo",
            external_content_id="SOURCE-001",
            alternate_ids={"ttarticle_id": "", "status_id": "5191839277071122"},
        )
