"""TikHub Runtime 一级评论/二级回复统一入口测试。"""

from __future__ import annotations

from aima_ugc.adapters.providers.tikhub.runtime import (
    advance_comments,
    advance_sub_comments,
    build_sub_comments_call,
    extract_sub_comment_items,
)


def test_sub_comment_calls_use_current_primary_operations() -> None:
    assert (
        build_sub_comments_call(
            platform="xhs",
            external_content_id="note-1",
            root_comment_id="comment-1",
        ).path
        == "/api/v1/xiaohongshu/app_v2/get_note_sub_comments"
    )
    assert (
        build_sub_comments_call(
            platform="douyin",
            external_content_id="aweme-1",
            root_comment_id="comment-1",
        ).path
        == "/api/v1/douyin/app/v3/fetch_video_comment_replies"
    )
    assert (
        build_sub_comments_call(
            platform="weibo",
            external_content_id="status-1",
            root_comment_id="comment-1",
        ).path
        == "/api/v1/weibo/web_v2/fetch_post_sub_comments"
    )
    assert (
        build_sub_comments_call(
            platform="bilibili",
            external_content_id="100010",
            root_comment_id="comment-1",
        ).path
        == "/api/v1/bilibili/app/fetch_reply_detail"
    )

    kuaishou = build_sub_comments_call(
        platform="kuaishou",
        external_content_id="photo-1",
        root_comment_id="comment-1",
    )
    assert kuaishou.path == "/api/v1/kuaishou/app/fetch_video_sub_comments"
    assert "/web/" not in kuaishou.path


def test_runtime_extracts_platform_specific_sub_comment_shapes() -> None:
    assert extract_sub_comment_items(
        "xhs", {"data": {"data": {"comments": [{"id": "xhs-reply"}]}}}
    ) == ({"id": "xhs-reply"},)
    assert extract_sub_comment_items(
        "douyin", {"data": {"comments": [{"cid": "douyin-reply"}]}}
    ) == ({"cid": "douyin-reply"},)
    assert extract_sub_comment_items(
        "weibo", {"data": {"data": [{"idstr": "weibo-reply"}], "max_id": 0}}
    ) == ({"idstr": "weibo-reply"},)
    assert extract_sub_comment_items(
        "bilibili",
        {"data": {"data": {"root": {"rpid_str": "root", "replies": [{"rpid_str": "reply"}]}}}},
    ) == ({"rpid_str": "reply"},)
    assert extract_sub_comment_items(
        "kuaishou", {"data": {"subComments": [{"commentId": "kuaishou-reply"}]}}
    ) == ({"commentId": "kuaishou-reply"},)


def test_comment_pagination_uses_existing_platform_state_models() -> None:
    xhs = advance_comments(
        platform="xhs",
        state={"cursor": "before", "index": 0, "page_area": "UNFOLDED"},
        body={
            "data": {
                "data": {
                    "comments": [{"id": "1"}],
                    "cursor": "after",
                    "index": 1,
                    "pageArea": "UNFOLDED",
                    "has_more": True,
                }
            }
        },
    )
    assert xhs.next_state == {"cursor": "after", "index": 1, "page_area": "UNFOLDED"}

    douyin = advance_comments(
        platform="douyin",
        state={"cursor": 0},
        body={"data": {"comments": [{"cid": "1"}], "cursor": 20, "has_more": 1}},
    )
    assert douyin.next_state == {"cursor": 20}

    weibo = advance_comments(
        platform="weibo",
        state={},
        body={
            "data": {
                "items": [{"data": {"idstr": "1"}}],
                "moreInfo": {"params": {"max_id": "20"}},
            }
        },
    )
    assert weibo.next_state == {"max_id": "20"}

    kuaishou = advance_comments(
        platform="kuaishou",
        state={"pcursor": ""},
        body={"data": {"rootComments": [{"commentId": "1"}], "pcursor": "next"}},
    )
    assert kuaishou.next_state == {"pcursor": "next"}


def test_sub_comment_pagination_stops_on_provider_exhaustion() -> None:
    assert (
        advance_sub_comments(
            platform="xhs",
            state={"cursor": "before", "index": 1, "page_area": "UNFOLDED"},
            body={
                "data": {"data": {"comments": [{"id": "1"}], "cursor": "end", "has_more": False}}
            },
        ).stop_reason
        == "provider_exhausted"
    )
    assert (
        advance_sub_comments(
            platform="douyin",
            state={"cursor": 0},
            body={"data": {"comments": [{"cid": "1"}], "cursor": 0, "has_more": 0}},
        ).stop_reason
        == "provider_exhausted"
    )
    assert (
        advance_sub_comments(
            platform="weibo",
            state={"max_id": ""},
            body={"data": {"data": [{"idstr": "1"}], "max_id": 0}},
        ).stop_reason
        == "provider_exhausted"
    )
    assert (
        advance_sub_comments(
            platform="kuaishou",
            state={"pcursor": "before"},
            body={"data": {"subComments": [], "pcursor": "after"}},
        ).stop_reason
        == "empty_page"
    )
