"""TikHub 真实二级评论/回复 Fixture → CanonicalCommentV1 回归测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from aima_ugc.adapters.providers.tikhub.mappers.bilibili import (
    BilibiliMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.bilibili import (
    map_comment as map_bilibili_comment,
)
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
    XiaohongshuMappingContext,
)
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    map_comment as map_xiaohongshu_comment,
)
from aima_ugc.adapters.providers.tikhub.operations import bilibili, kuaishou

_ROOT = Path("tests/fixtures/providers/tikhub")
_OBSERVED_AT = datetime(2026, 8, 15, 20, 0, tzinfo=UTC)
_RAW_ID = UUID("00000000-0000-0000-0000-000000000704")


def _fixture(platform: str, name: str) -> dict[str, object]:
    return json.loads((_ROOT / platform / name).read_text(encoding="utf-8"))


def test_xiaohongshu_real_sub_comment_preserves_root_and_direct_parent() -> None:
    raw = _fixture("xiaohongshu", "sub_comments_page1.sanitized.json")["data"]["data"]["comments"][
        0
    ]
    mapped = map_xiaohongshu_comment(
        raw,
        XiaohongshuMappingContext(
            provider_request_id="request-reply-1",
            provider_attempt_id="attempt-reply-1",
            raw_artifact_id=_RAW_ID,
            operation="get_note_sub_comments",
            source_type="comment",
            source_value="xiaohongshu-comment-root-1",
            observed_at=_OBSERVED_AT,
            root_comment_id="xiaohongshu-comment-root-1",
        ),
        item_locator="data.data.comments[0]",
        is_root=False,
    )
    assert mapped.root_comment_id == "xiaohongshu-comment-root-1"
    assert mapped.parent_comment_id == "xiaohongshu-comment-root-1"
    assert mapped.external_comment_id == "xiaohongshu-comment-reply-2"


def test_douyin_real_reply_prefers_direct_reply_to_reply_parent() -> None:
    raw = _fixture("douyin", "replies_page1.sanitized.json")["data"]["comments"][0]
    mapped = map_douyin_comment(
        raw,
        DouyinMappingContext(
            provider_request_id="request-reply-1",
            provider_attempt_id="attempt-reply-1",
            raw_artifact_id=_RAW_ID,
            operation="fetch_video_comment_replies",
            source_type="comment",
            source_value="douyin-comment-root-1",
            observed_at=_OBSERVED_AT,
            external_content_id="douyin-aweme-1",
            root_comment_id="douyin-comment-root-1",
        ),
        item_locator="data.comments[0]",
        is_root=False,
    )
    assert mapped.root_comment_id == "douyin-comment-root-1"
    assert mapped.parent_comment_id == "douyin-comment-parent-1"
    assert mapped.external_comment_id == "douyin-comment-reply-1"


def test_weibo_real_sub_comment_uses_reply_comment_as_direct_parent() -> None:
    raw = _fixture("weibo", "sub_comments_page1.sanitized.json")["data"]["data"][0]
    mapped = map_weibo_comment(
        raw,
        WeiboMappingContext(
            provider_request_id="request-reply-1",
            provider_attempt_id="attempt-reply-1",
            raw_artifact_id=_RAW_ID,
            operation="fetch_post_sub_comments",
            source_type="comment",
            source_value="weibo-comment-root-1",
            observed_at=_OBSERVED_AT,
            external_content_id="weibo-status-1",
            root_comment_id="weibo-comment-root-1",
        ),
        item_locator="data.data[0]",
        is_root=False,
    )
    assert mapped.root_comment_id == "weibo-comment-root-1"
    assert mapped.parent_comment_id == "weibo-comment-root-1"
    assert mapped.external_comment_id == "weibo-comment-reply-1"


def test_bilibili_real_root_and_reply_map_numeric_ids_to_string_tree() -> None:
    body = _fixture("bilibili", "replies_page1.sanitized.json")
    root, replies = bilibili.extract_reply_detail(body)
    context = BilibiliMappingContext(
        provider_request_id="request-reply-1",
        provider_attempt_id="attempt-reply-1",
        raw_artifact_id=_RAW_ID,
        operation="fetch_reply_detail",
        source_type="content",
        source_value="100010",
        observed_at=_OBSERVED_AT,
        external_content_id="100010",
    )
    root_mapped = map_bilibili_comment(
        root,
        context,
        item_locator="data.data.root",
        is_root=True,
    )
    assert root_mapped.external_comment_id == "bili-comment-root-1"
    assert root_mapped.root_comment_id == "bili-comment-root-1"
    assert root_mapped.parent_comment_id is None
    assert root_mapped.metrics.like_count == 377
    assert root_mapped.metrics.reply_count == 8

    reply_mapped = map_bilibili_comment(
        replies[0],
        BilibiliMappingContext(
            provider_request_id=context.provider_request_id,
            provider_attempt_id=context.provider_attempt_id,
            raw_artifact_id=context.raw_artifact_id,
            operation=context.operation,
            source_type=context.source_type,
            source_value=context.source_value,
            observed_at=context.observed_at,
            external_content_id="100010",
            root_comment_id="bili-comment-root-1",
        ),
        item_locator="data.data.root.replies[0]",
        is_root=False,
    )
    assert reply_mapped.external_comment_id == "bili-comment-reply-1"
    assert reply_mapped.root_comment_id == "bili-comment-root-1"
    assert reply_mapped.parent_comment_id == "bili-comment-root-1"


def test_kuaishou_real_sub_comment_maps_nonempty_web_reply_without_guessing_parent() -> None:
    body = _fixture("kuaishou", "sub_comments_page1.sanitized.json")
    replies = kuaishou.extract_sub_comment_items(body)
    assert len(replies) == 2

    mapped = map_kuaishou_comment(
        replies[0],
        KuaishouMappingContext(
            provider_request_id="request-reply-1",
            provider_attempt_id="attempt-reply-1",
            raw_artifact_id=_RAW_ID,
            operation="fetch_one_video_sub_comment",
            source_type="comment",
            source_value="kuaishou-comment-root-real",
            observed_at=_OBSERVED_AT,
            external_content_id="100001",
            root_comment_id="kuaishou-comment-root-real",
        ),
        item_locator="data.subComments[0]",
        is_root=False,
    )

    assert mapped.external_content_id == "100001"
    assert mapped.external_comment_id == "100002"
    assert mapped.root_comment_id == "kuaishou-comment-root-real"
    assert mapped.parent_comment_id is None
    assert mapped.metrics.like_count == 15
    assert mapped.author is not None
    assert mapped.author.external_account_id == "100003"

    pagination = kuaishou.KuaishouCursorPagination.from_response(
        previous_cursor="cursor-before", body=body, item_key="subComments"
    )
    assert pagination.should_continue is True
    assert pagination.next_cursor == "1018975453518"
