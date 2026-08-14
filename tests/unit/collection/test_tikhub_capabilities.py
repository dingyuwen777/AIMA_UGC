"""Stage 7 TikHub 当前机器 Capability 测试。"""

from __future__ import annotations

import json

from aima_ugc.adapters.providers.tikhub.capabilities import XHS_TIKHUB_CAPABILITY
from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import (
    build_image_detail_request,
    build_note_comments_request,
    build_search_notes_request,
    build_sub_comments_request,
    build_video_detail_request,
)


def _operation(name: str):
    return next(
        operation
        for operation in XHS_TIKHUB_CAPABILITY.operations
        if operation.business_operation == name
    )


def test_xhs_tikhub_capability_matches_current_stage6_operations() -> None:
    assert XHS_TIKHUB_CAPABILITY.schema_version == "provider-platform-capability.v1"
    assert XHS_TIKHUB_CAPABILITY.provider == "tikhub"
    assert XHS_TIKHUB_CAPABILITY.platform == "xhs"

    search = _operation("keyword_search")
    assert search.provider_operations == ("search_notes",)
    assert set(search.supported_sort_modes) == {
        "general",
        "latest",
        "most_liked",
        "most_commented",
        "most_collected",
        "english_preferred",
    }
    assert set(search.supported_time_filters) == {"all", "1d", "7d", "180d"}
    assert set(search.supported_content_types) == {"all", "video", "image", "live"}
    assert search.native_time_filter is True
    assert search.observes_comment_count is True

    detail = _operation("content_detail")
    assert detail.provider_operations == ("get_image_note_detail", "get_video_note_detail")
    assert detail.observes_comment_count is True

    comments = _operation("comments")
    assert comments.provider_operations == ("get_note_comments",)
    assert "latest" in comments.comment_sort_modes
    assert comments.supports_reply_count is True
    assert comments.supports_sub_comments is True
    # 当前没有非空真实评论 Fixture 证明“遇到已知 comment_id 即可安全停”，保守关闭增量资格。
    assert comments.supports_incremental_comment_sort is False

    replies = _operation("sub_comments")
    assert replies.provider_operations == ("get_note_sub_comments",)


def test_xhs_capability_operation_names_stay_aligned_with_request_builders() -> None:
    assert build_search_notes_request(
        keyword="爱玛", page=1, sort_type="time_descending", time_filter="一天内"
    ).path.endswith("/search_notes")
    assert build_image_detail_request(note_id="note-1").path.endswith("/get_image_note_detail")
    assert build_video_detail_request(note_id="note-1").path.endswith("/get_video_note_detail")
    assert build_note_comments_request(note_id="note-1").path.endswith("/get_note_comments")
    assert build_sub_comments_request(note_id="note-1", comment_id="comment-1").path.endswith(
        "/get_note_sub_comments"
    )


def test_business_capability_never_exposes_provider_pagination_or_secret_fields() -> None:
    payload = json.dumps(XHS_TIKHUB_CAPABILITY.model_dump(mode="json"), ensure_ascii=False)
    for forbidden in (
        "search_id",
        "search_session_id",
        "pagearea",
        "max_id",
        "authorization",
        "api_key",
        "apikey",
        "cookie",
        "token",
    ):
        assert forbidden not in payload.casefold()
