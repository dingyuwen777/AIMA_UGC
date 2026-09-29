"""TikHub 同业务语义备用 Operation。

本模块只保存已经由 TikHub 当前官方接口事实确认的备用请求构造。备用接口不进入默认
Capability；调用方只有在显式补采策略下才可启用，并且必须产生独立 Provider Attempt、
Pricing/Budget 预留和 Raw 证据。抖音账号全量评论 Runner 会在 App V3 未对齐时使用 Web 备用。
"""

from __future__ import annotations

from aima_ugc.adapters.providers.tikhub.operations.bilibili import BilibiliRequest
from aima_ugc.adapters.providers.tikhub.operations.douyin import DouyinRequest
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import KuaishouRequest
from aima_ugc.adapters.providers.tikhub.operations.weibo import WeiboRequest


def build_douyin_web_v2_detail_backup_request(*, aweme_id: str) -> DouyinRequest:
    """抖音 Web V2 详情备用；正式主链仍使用 App V3。"""
    return DouyinRequest(
        method="GET",
        path="/api/v1/douyin/web/fetch_one_video_v2",
        params={"aweme_id": _required_text(aweme_id, "aweme_id")},
    )


def build_douyin_douplus_user_posts_backup_request(
    *, sec_uid: str, cursor: str = "0", count: int = 10
) -> DouyinRequest:
    """Dou+ 简洁用户作品接口；用于 App/Web 主页作品接口返回 400 时补采。"""

    _positive(count, "count")
    normalized_cursor = _required_text(cursor, "cursor")
    if not normalized_cursor.isdigit():
        raise ValueError("cursor 必须是非负整数字符串")
    return DouyinRequest(
        method="POST",
        path="/api/v1/douyin/douplus/fetch_user_posts",
        params={},
        body={
            "sec_uid": _required_text(sec_uid, "sec_uid"),
            "cursor": normalized_cursor,
            "count": count,
        },
    )


def build_douyin_web_comments_backup_request(
    *, aweme_id: str, cursor: int = 0, count: int = 50
) -> DouyinRequest:
    """抖音 Web 一级评论备用；实测接口单页上限为 50。"""
    _nonnegative(cursor, "cursor")
    _positive(count, "count")
    if count > 50:
        raise ValueError("count 不能大于抖音 Web 评论接口实测上限 50")
    return DouyinRequest(
        method="GET",
        path="/api/v1/douyin/web/fetch_video_comments",
        params={
            "aweme_id": _required_text(aweme_id, "aweme_id"),
            "cursor": cursor,
            "count": count,
        },
    )


def build_douyin_web_replies_backup_request(
    *, item_id: str, comment_id: str, cursor: int = 0, count: int = 100
) -> DouyinRequest:
    """抖音 Web 评论回复备用；较大分页用于补齐 App V3 回复。"""
    _nonnegative(cursor, "cursor")
    _positive(count, "count")
    return DouyinRequest(
        method="GET",
        path="/api/v1/douyin/web/fetch_video_comment_replies",
        params={
            "item_id": _required_text(item_id, "item_id"),
            "comment_id": _required_text(comment_id, "comment_id"),
            "cursor": cursor,
            "count": count,
        },
    )


def build_weibo_web_v2_detail_backup_request(*, status_id: str) -> WeiboRequest:
    """微博 Web V2 详情备用；默认请求长微博全文。"""
    return WeiboRequest(
        method="GET",
        path="/api/v1/weibo/web_v2/fetch_post_detail",
        params={
            "id": _required_text(status_id, "status_id"),
            "is_get_long_text": "true",
        },
    )


def build_weibo_web_replies_backup_request(
    *, root_comment_id: str, max_id: str = "0"
) -> WeiboRequest:
    """微博 Web 评论回复备用；正式主链仍使用 Web V2 二级评论。"""
    return WeiboRequest(
        method="GET",
        path="/api/v1/weibo/web/fetch_comment_replies",
        params={
            "cid": _required_text(root_comment_id, "root_comment_id"),
            "max_id": max_id,
        },
    )


def build_bilibili_web_detail_backup_request(*, aid: str) -> BilibiliRequest:
    """B站 Web AID 详情备用；正式主链仍使用 App fetch_one_video。"""
    return BilibiliRequest(
        method="GET",
        path="/api/v1/bilibili/web/fetch_video_detail",
        params={"aid": _required_text(aid, "aid")},
    )


def build_kuaishou_web_v2_detail_backup_request(*, photo_id: str) -> KuaishouRequest:
    """快手 Web V2 详情备用；正式主链仍使用 App fetch_one_video。"""
    return KuaishouRequest(
        method="GET",
        path="/api/v1/kuaishou/web/fetch_one_video_v2",
        params={"photo_id": _required_text(photo_id, "photo_id")},
    )


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


def _nonnegative(value: int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} 不能小于 0")


def _positive(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} 必须是正整数")


__all__ = [
    "build_bilibili_web_detail_backup_request",
    "build_douyin_douplus_user_posts_backup_request",
    "build_douyin_web_comments_backup_request",
    "build_douyin_web_replies_backup_request",
    "build_douyin_web_v2_detail_backup_request",
    "build_kuaishou_web_v2_detail_backup_request",
    "build_weibo_web_replies_backup_request",
    "build_weibo_web_v2_detail_backup_request",
]
