"""TikHub 真实一级评论 Fixture → CanonicalCommentV1 回归测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from aima_ugc.adapters.providers.tikhub.mappers.douyin import (
    DouyinMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.douyin import (
    map_comment as map_douyin_comment,
)
from aima_ugc.adapters.providers.tikhub.mappers.kuaishou import (
    KuaishouMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.kuaishou import (
    map_comment as map_kuaishou_comment,
)
from aima_ugc.adapters.providers.tikhub.mappers.weibo import (
    WeiboMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.weibo import (
    map_comment as map_weibo_comment,
)
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    XhsMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    map_comment as map_xhs_comment,
)

_FIXTURE_ROOT = Path("tests/fixtures/providers/tikhub")
_OBSERVED_AT = datetime(2026, 8, 15, 18, 0, tzinfo=UTC)
_RAW_ID = UUID("00000000-0000-0000-0000-000000000702")


def _fixture(platform: str) -> dict[str, object]:
    return json.loads(
        (_FIXTURE_ROOT / platform / "comments_page1.sanitized.json").read_text(encoding="utf-8")
    )


def _common_context(context_type: type, operation: str, content_id: str):
    return context_type(
        provider_request_id="request-comment-fixture-1",
        provider_attempt_id="attempt-comment-fixture-1",
        raw_artifact_id=_RAW_ID,
        operation=operation,
        source_type="content",
        source_value=content_id,
        observed_at=_OBSERVED_AT,
        external_content_id=content_id,
    )


def test_xhs_real_root_and_embedded_reply_map_comment_tree() -> None:
    root = _fixture("xhs")["data"]["data"]["comments"][0]
    context = XhsMappingContext(
        provider_request_id="request-comment-fixture-1",
        provider_attempt_id="attempt-comment-fixture-1",
        raw_artifact_id=_RAW_ID,
        operation="get_note_comments",
        source_type="content",
        source_value="xhs-note-1",
        observed_at=_OBSERVED_AT,
    )
    root_mapped = map_xhs_comment(
        root,
        context,
        item_locator="data.data.comments[0]",
        is_root=True,
    )
    assert root_mapped.external_content_id == "xhs-note-1"
    assert root_mapped.external_comment_id == "xhs-comment-root-1"
    assert root_mapped.root_comment_id == "xhs-comment-root-1"
    assert root_mapped.parent_comment_id is None
    assert root_mapped.metrics.like_count == 145
    assert root_mapped.metrics.reply_count == 119

    reply = root["sub_comments"][0]
    reply_context = XhsMappingContext(
        provider_request_id=context.provider_request_id,
        provider_attempt_id=context.provider_attempt_id,
        raw_artifact_id=context.raw_artifact_id,
        operation=context.operation,
        source_type=context.source_type,
        source_value=context.source_value,
        observed_at=context.observed_at,
        root_comment_id="xhs-comment-root-1",
    )
    reply_mapped = map_xhs_comment(
        reply,
        reply_context,
        item_locator="data.data.comments[0].sub_comments[0]",
        is_root=False,
    )
    assert reply_mapped.root_comment_id == "xhs-comment-root-1"
    assert reply_mapped.parent_comment_id == "xhs-comment-root-1"
    assert reply_mapped.external_comment_id == "xhs-comment-reply-1"


def test_douyin_real_root_comment_maps_to_canonical_tree_root() -> None:
    raw = _fixture("douyin")["data"]["comments"][0]
    mapped = map_douyin_comment(
        raw,
        _common_context(DouyinMappingContext, "fetch_video_comments", "douyin-aweme-1"),
        item_locator="data.comments[0]",
        is_root=True,
    )
    assert mapped.platform == "douyin"
    assert mapped.external_content_id == "douyin-aweme-1"
    assert mapped.external_comment_id == "douyin-comment-root-1"
    assert mapped.root_comment_id == "douyin-comment-root-1"
    assert mapped.parent_comment_id is None
    assert mapped.author is not None
    assert mapped.author.external_account_id == "douyin-user-1"
    assert mapped.metrics.like_count == 3
    assert mapped.metrics.reply_count == 2


def test_weibo_real_root_comment_uses_request_content_id_not_comment_rootid() -> None:
    raw = _fixture("weibo")["data"]["items"][0]["data"]
    mapped = map_weibo_comment(
        raw,
        _common_context(WeiboMappingContext, "fetch_status_comments", "weibo-status-1"),
        item_locator="data.items[0].data",
        is_root=True,
    )
    assert mapped.platform == "weibo"
    assert mapped.external_content_id == "weibo-status-1"
    assert mapped.external_comment_id == "weibo-comment-root-1"
    assert mapped.root_comment_id == "weibo-comment-root-1"
    assert mapped.parent_comment_id is None
    assert mapped.author is not None
    assert mapped.author.external_account_id == "weibo-user-1"
    assert mapped.metrics.like_count == 762
    assert mapped.metrics.reply_count == 2


def test_kuaishou_real_root_comment_converts_numeric_ids_to_strings() -> None:
    raw = _fixture("kuaishou")["data"]["rootComments"][0]
    mapped = map_kuaishou_comment(
        raw,
        _common_context(KuaishouMappingContext, "fetch_one_video_comment", "100003"),
        item_locator="data.rootComments[0]",
        is_root=True,
    )
    assert mapped.platform == "kuaishou"
    assert mapped.external_content_id == "100003"
    assert mapped.external_comment_id == "100002"
    assert mapped.root_comment_id == "100002"
    assert mapped.parent_comment_id is None
    assert mapped.author is not None
    assert mapped.author.external_account_id == "100004"
    assert mapped.metrics.like_count == 7
    assert mapped.published_at == datetime.fromtimestamp(1720000000, tz=UTC)
