"""Stage 6 小红书 TikHub App V2 Mapper 行为测试。"""

from datetime import UTC, datetime
from uuid import UUID

from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    XhsMappingContext,
    map_comment,
    map_content,
)
from aima_ugc.contracts.canonical import CanonicalCommentV1, CanonicalContentV1

OBSERVED_AT = datetime(2026, 8, 5, 10, 0, 12, tzinfo=UTC)
RAW_ARTIFACT_ID = UUID("00000000-0000-0000-0000-000000000101")


def _context(*, operation: str, root_comment_id: str | None = None) -> XhsMappingContext:
    return XhsMappingContext(
        provider_request_id="request-1",
        provider_attempt_id="attempt-1",
        raw_artifact_id=RAW_ARTIFACT_ID,
        operation=operation,
        source_type="keyword_search",
        source_value="爱玛",
        observed_at=OBSERVED_AT,
        root_comment_id=root_comment_id,
    )


def test_real_search_wrapper_maps_observed_content_fields() -> None:
    raw = {
        "model_type": "note",
        "note": {
            "id": "note-1",
            "type": "normal",
            "title": "脱敏标题",
            "desc": "脱敏正文",
            "timestamp": 1785920000,
            "update_time": 1785920060000,
            "liked_count": 12,
            "comments_count": 3,
            "collected_count": 4,
            "shared_count": 2,
            "user": {
                "userid": "user-1",
                "red_id": "red-1",
                "nickname": "脱敏用户",
                "red_official_verified": False,
            },
        },
    }
    result = map_content(raw, _context(operation="search_notes"), item_locator="note:note-1")
    assert isinstance(result, CanonicalContentV1)
    assert result.platform == "xhs"
    assert result.external_content_id == "note-1"
    assert result.content_type == "image"
    assert result.metrics.like_count == 12
    assert result.metrics.comment_count == 3
    assert result.metrics.favorite_count == 4
    assert result.metrics.share_count == 2
    assert result.author is not None
    assert result.author.external_account_id == "user-1"
    assert result.author.alternate_ids == {"red_id": "red-1"}
    assert result.author.verified is False
    assert "text" in result.observed_fields
    assert "source_updated_at" in result.observed_fields
    assert "author.alternate_ids" in result.observed_fields
    assert "metrics.like_count" in result.observed_fields
    assert result.source.item_locator == "note:note-1"
    assert result.source.provider_name == "tikhub"


def test_mapper_does_not_invent_missing_or_blank_fields() -> None:
    result = map_content(
        {"note": {"id": "note-2", "type": "video", "title": "", "desc": ""}},
        _context(operation="search_notes"),
        item_locator="note:note-2",
    )
    assert result.published_at is None
    assert result.title is None
    assert result.text is None
    assert result.metrics.like_count is None
    assert "published_at" not in result.observed_fields
    assert "title" not in result.observed_fields
    assert "text" not in result.observed_fields
    assert "metrics.like_count" not in result.observed_fields


def test_root_comment_has_no_direct_parent() -> None:
    result = map_comment(
        {
            "id": "comment-root",
            "note_id": "note-1",
            "content": "一级评论",
            "like_count": 5,
            "user_info": {"user_id": "user-2", "nickname": "评论者"},
        },
        _context(operation="get_note_comments"),
        item_locator="comment:comment-root",
        is_root=True,
    )
    assert isinstance(result, CanonicalCommentV1)
    assert result.root_comment_id == "comment-root"
    assert result.parent_comment_id is None


def test_sub_comment_context_sets_thread_root_but_does_not_guess_direct_parent() -> None:
    result = map_comment(
        {
            "id": "comment-child",
            "note_id": "note-1",
            "content": "回复",
        },
        _context(operation="get_note_sub_comments", root_comment_id="comment-root"),
        item_locator="comment:comment-child",
        is_root=False,
    )
    assert result.root_comment_id == "comment-root"
    assert result.parent_comment_id is None


def test_explicit_target_comment_maps_direct_parent() -> None:
    result = map_comment(
        {
            "id": "comment-child-2",
            "note_id": "note-1",
            "content": "回复另一个回复",
            "target_comment": {"id": "comment-child"},
        },
        _context(operation="get_note_sub_comments", root_comment_id="comment-root"),
        item_locator="comment:comment-child-2",
        is_root=False,
    )
    assert result.root_comment_id == "comment-root"
    assert result.parent_comment_id == "comment-child"
