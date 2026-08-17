"""TikHub 抖音 Raw → Canonical 纯 Mapper。"""

from __future__ import annotations

from typing import Any

from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalCommentV1,
    CanonicalContentV1,
    CanonicalMediaV1,
    CanonicalMetricsV1,
)

from .common import (
    TikHubMappingContext,
    count,
    first_dict,
    http_url,
    optional_string,
    required_string,
    source,
    timestamp,
)

DouyinMappingContext = TikHubMappingContext


def map_content(
    raw: dict[str, Any], context: DouyinMappingContext, *, item_locator: str
) -> CanonicalContentV1:
    """把真实 Search V2 或 App V3 Detail 映射为内容 Observation。"""
    data = first_dict(raw, "data")
    item = first_dict(data, "aweme_info")
    if not item:
        item = raw if "aweme_id" in raw else {}
    if not item:
        raise ValueError("抖音内容缺少 aweme_info/aweme_id")

    external_id = required_string(item, "aweme_id")
    observed_fields: list[str] = ["content_type"]

    alternate_ids: dict[str, str] = {}
    group_id = optional_string(item, "group_id")
    if group_id is not None and group_id != external_id:
        alternate_ids["group_id"] = group_id
        observed_fields.append("alternate_ids")

    title = optional_string(item, "item_title")
    text = optional_string(item, "desc")
    if title is not None:
        observed_fields.append("title")
    if text is not None:
        observed_fields.append("text")

    share_url = http_url(item, "share_url")
    if share_url is not None:
        observed_fields.append("share_url")

    author_raw = first_dict(item, "author")
    author, author_fields = _map_author(author_raw)
    observed_fields.extend(f"author.{field}" for field in author_fields)

    metrics, metric_fields = _map_metrics(first_dict(item, "statistics"))
    observed_fields.extend(f"metrics.{field}" for field in metric_fields)

    published_at = timestamp(item, "create_time")
    if published_at is not None:
        observed_fields.append("published_at")

    media = _map_media(item)
    if media:
        observed_fields.append("media")

    return CanonicalContentV1(
        platform="douyin",
        external_content_id=external_id,
        alternate_ids=alternate_ids,
        content_type=_content_type(item),
        title=title,
        text=text,
        share_url=share_url,
        author=author,
        published_at=published_at,
        observed_at=context.observed_at,
        media=media,
        metrics=metrics,
        source=source(context, item_locator),
        observed_fields=observed_fields,
    )


def map_comment(
    raw: dict[str, Any],
    context: DouyinMappingContext,
    *,
    item_locator: str,
    is_root: bool,
) -> CanonicalCommentV1:
    """把真实 App V3 comment/reply 映射为统一评论树节点。"""
    external_comment_id = required_string(raw, "cid")
    external_content_id = optional_string(raw, "aweme_id") or context.external_content_id
    if external_content_id is None:
        raise ValueError("抖音评论缺少 aweme_id 且上下文未提供 external_content_id")

    observed_fields: list[str] = []
    text = optional_string(raw, "text")
    if text is not None:
        observed_fields.append("text")

    author, author_fields = _map_author(first_dict(raw, "user"))
    observed_fields.extend(f"author.{field}" for field in author_fields)

    like_count, like_observed = count(raw, "digg_count")
    reply_count, reply_observed = count(raw, "reply_comment_total", "comment_reply_total")
    if like_observed:
        observed_fields.append("metrics.like_count")
    if reply_observed:
        observed_fields.append("metrics.reply_count")

    published_at = timestamp(raw, "create_time")
    if published_at is not None:
        observed_fields.append("published_at")

    root_comment_id: str | None
    parent_comment_id: str | None
    if is_root:
        root_comment_id = external_comment_id
        parent_comment_id = None
        observed_fields.extend(("root_comment_id", "parent_comment_id"))
    else:
        root_comment_id = context.root_comment_id or optional_string(raw, "root_comment_id")
        parent_comment_id = _douyin_parent_comment_id(raw)
        if root_comment_id is not None:
            observed_fields.append("root_comment_id")
        if parent_comment_id is not None:
            observed_fields.append("parent_comment_id")

    return CanonicalCommentV1(
        platform="douyin",
        external_content_id=external_content_id,
        external_comment_id=external_comment_id,
        root_comment_id=root_comment_id,
        parent_comment_id=parent_comment_id,
        author=author,
        text=text,
        published_at=published_at,
        observed_at=context.observed_at,
        metrics=CanonicalMetricsV1(like_count=like_count, reply_count=reply_count),
        source=source(context, item_locator),
        observed_fields=observed_fields,
    )


def _douyin_parent_comment_id(raw: dict[str, Any]) -> str | None:
    reply_to_reply_id = optional_string(raw, "reply_to_reply_id")
    if reply_to_reply_id not in {None, "0"}:
        return reply_to_reply_id
    reply_id = optional_string(raw, "reply_id")
    if reply_id not in {None, "0"}:
        return reply_id
    return None


def _content_type(item: dict[str, Any]) -> str:
    if first_dict(item, "video"):
        return "video"
    for key in ("images", "image_list", "image_infos"):
        value = item.get(key)
        if isinstance(value, list) and value:
            return "image"
    return "unknown"


def _map_media(item: dict[str, Any]) -> list[CanonicalMediaV1]:
    video = first_dict(item, "video")
    if video:
        duration, _ = count(video, "duration")
        width, _ = count(video, "width")
        height, _ = count(video, "height")
        return [
            CanonicalMediaV1(
                media_type="video",
                width=width,
                height=height,
                duration_ms=duration,
            )
        ]
    return []


def _map_author(raw: dict[str, Any]) -> tuple[CanonicalAuthorV1 | None, tuple[str, ...]]:
    if not raw:
        return None, ()
    external_id = optional_string(raw, "uid")
    sec_uid = optional_string(raw, "sec_uid")
    handle = optional_string(raw, "unique_id")
    display_name = optional_string(raw, "nickname")
    verification_label = optional_string(raw, "enterprise_verify_reason")

    alternate_ids: dict[str, str] = {}
    fields: list[str] = []
    if external_id is not None:
        fields.append("external_account_id")
    if sec_uid is not None:
        alternate_ids["sec_uid"] = sec_uid
        fields.append("alternate_ids")
    if handle is not None:
        fields.append("handle")
    if display_name is not None:
        fields.append("display_name")
    if verification_label is not None:
        fields.append("verification_label")
    if not fields:
        return None, ()

    return (
        CanonicalAuthorV1(
            external_account_id=external_id,
            alternate_ids=alternate_ids,
            handle=handle,
            display_name=display_name,
            verification_label=verification_label,
        ),
        tuple(fields),
    )


def _map_metrics(raw: dict[str, Any]) -> tuple[CanonicalMetricsV1, tuple[str, ...]]:
    mappings = {
        "like_count": ("digg_count",),
        "comment_count": ("comment_count",),
        "favorite_count": ("collect_count",),
        "share_count": ("share_count",),
        "repost_count": ("forward_count",),
        "play_count": ("play_count",),
        "download_count": ("download_count",),
    }
    values: dict[str, int | None] = {}
    observed: list[str] = []
    for canonical, keys in mappings.items():
        value, present = count(raw, *keys)
        values[canonical] = value
        if present:
            observed.append(canonical)
    return (
        CanonicalMetricsV1(
            like_count=values["like_count"],
            comment_count=values["comment_count"],
            favorite_count=values["favorite_count"],
            share_count=values["share_count"],
            repost_count=values["repost_count"],
            play_count=values["play_count"],
            download_count=values["download_count"],
        ),
        tuple(observed),
    )


__all__ = ["DouyinMappingContext", "map_comment", "map_content"]
