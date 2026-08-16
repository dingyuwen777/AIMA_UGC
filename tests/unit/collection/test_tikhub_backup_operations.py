"""TikHub 显式备用 Operation 请求合同。"""

import pytest
from aima_ugc.adapters.providers.tikhub.operations.backup import (
    build_bilibili_web_detail_backup_request,
    build_douyin_web_comments_backup_request,
    build_douyin_web_replies_backup_request,
    build_douyin_web_v2_detail_backup_request,
    build_kuaishou_web_v2_detail_backup_request,
    build_weibo_web_replies_backup_request,
    build_weibo_web_v2_detail_backup_request,
)


def test_douyin_web_backup_requests_keep_same_business_identity() -> None:
    detail = build_douyin_web_v2_detail_backup_request(aweme_id="aweme-1")
    comments = build_douyin_web_comments_backup_request(aweme_id="aweme-1")
    replies = build_douyin_web_replies_backup_request(
        item_id="aweme-1",
        comment_id="comment-1",
    )

    assert detail.path == "/api/v1/douyin/web/fetch_one_video_v2"
    assert detail.params == {"aweme_id": "aweme-1"}
    assert comments.path == "/api/v1/douyin/web/fetch_video_comments"
    assert comments.params == {"aweme_id": "aweme-1", "cursor": 0}
    assert "count" not in comments.params
    assert replies.path == "/api/v1/douyin/web/fetch_video_comment_replies"
    assert replies.params == {
        "item_id": "aweme-1",
        "comment_id": "comment-1",
        "cursor": 0,
    }
    assert "count" not in replies.params


def test_weibo_web_v2_detail_and_web_reply_backups_keep_business_identity() -> None:
    detail = build_weibo_web_v2_detail_backup_request(status_id="status-1")
    replies = build_weibo_web_replies_backup_request(root_comment_id="comment-root")

    assert detail.path == "/api/v1/weibo/web_v2/fetch_post_detail"
    assert detail.params == {"id": "status-1", "is_get_long_text": "true"}
    assert replies.path == "/api/v1/weibo/web/fetch_comment_replies"
    assert replies.params == {"cid": "comment-root", "max_id": "0"}


def test_bilibili_and_kuaishou_web_detail_backups_reuse_primary_ids() -> None:
    bilibili = build_bilibili_web_detail_backup_request(aid="123456")
    kuaishou = build_kuaishou_web_v2_detail_backup_request(photo_id="photo-1")

    assert bilibili.path == "/api/v1/bilibili/web/fetch_video_detail"
    assert bilibili.params == {"aid": "123456"}
    assert kuaishou.path == "/api/v1/kuaishou/web/fetch_one_video_v2"
    assert kuaishou.params == {"photo_id": "photo-1"}


def test_backup_operations_fail_closed_on_empty_ids_or_negative_cursor() -> None:
    with pytest.raises(ValueError, match="aweme_id"):
        build_douyin_web_v2_detail_backup_request(aweme_id=" ")
    with pytest.raises(ValueError, match="cursor"):
        build_douyin_web_comments_backup_request(aweme_id="1", cursor=-1)
    with pytest.raises(ValueError, match="comment_id"):
        build_douyin_web_replies_backup_request(item_id="1", comment_id=" ")
    with pytest.raises(ValueError, match="status_id"):
        build_weibo_web_v2_detail_backup_request(status_id="")
    with pytest.raises(ValueError, match="root_comment_id"):
        build_weibo_web_replies_backup_request(root_comment_id="")
    with pytest.raises(ValueError, match="aid"):
        build_bilibili_web_detail_backup_request(aid="")
    with pytest.raises(ValueError, match="photo_id"):
        build_kuaishou_web_v2_detail_backup_request(photo_id="")
