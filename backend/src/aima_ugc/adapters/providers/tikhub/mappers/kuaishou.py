"""TikHub 快手 Raw → Canonical 纯 Mapper。"""

from __future__ import annotations

from typing import Any

from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalCommentV1,
    CanonicalContentV1,
    CanonicalMetricsV1,
)

from .common import (
    TikHubMappingContext,
    count,
    first_dict,
    optional_bool,
    optional_string,
    required_string,
    source,
    timestamp,
)

KuaishouMappingContext = TikHubMappingContext


def map_content(
    raw: dict[str, Any], context: KuaishouMappingContext, *, item_locator: str
) -> CanonicalContentV1:
    """把真实 App Search V2 feed 或 Detail photo 映射为内容 Observation。"""
    item = first_dict(raw, "feed") or raw
    if "photo_id" not in item:
        raise ValueError("快手内容缺少 photo_id")

    external_id = required_string(item, "photo_id")
    observed_fields: list[str] = ["content_type"]

    alternate_ids: dict[str, str] = {}
    kwai_id = optional_string(item, "kwaiId", "kwai_id")
    if kwai_id is not None:
        alternate_ids["kwai_id"] = kwai_id
        observed_fields.append("alternate_ids")

    text = optional_string(item, "caption")
    if text is not None:
        observed_fields.append("text")

    author, author_fields = _map_content_author(item)
    observed_fields.extend(f"author.{field}" for field in author_fields)

    metrics, metric_fields = _map_metrics(item)
    observed_fields.extend(f"metrics.{field}" for field in metric_fields)

    published_at = timestamp(item, "timestamp")
    if published_at is not None:
        observed_fields.append("published_at")

    return CanonicalContentV1(
        platform="kuaishou",
        external_content_id=external_id,
        alternate_ids=alternate_ids,
        content_type=_content_type(item),
        text=text,
        author=author,
        published_at=published_at,
        observed_at=context.observed_at,
        metrics=metrics,
        source=source(context, item_locator),
        observed_fields=observed_fields,
    )


def map_comment(
    raw: dict[str, Any],
    context: KuaishouMappingContext,
    *,
    item_locator: str,
    is_root: bool,
) -> CanonicalCommentV1:
    """把真实 Web rootComments/sub-comments 映射为统一评论树节点。"""
    external_comment_id = required_string(raw, "comment_id")
    external_content_id = optional_string(raw, "photo_id") or context.external_content_id
    if external_content_id is None:
        raise ValueError("快手评论缺少 photo_id 且上下文未提供 external_content_id")

    author = _map_comment_author(raw)
    like_count, _ = count(raw, "likedCount", "like_count")

    if is_root:
        root_comment_id = external_comment_id
        parent_comment_id = None
    else:
        root_comment_id = context.root_comment_id
        parent_comment_id = _kuaishou_parent_comment_id(raw, root_comment_id)

    return CanonicalCommentV1(
        platform="kuaishou",
        external_content_id=external_content_id,
        external_comment_id=external_comment_id,
        root_comment_id=root_comment_id,
        parent_comment_id=parent_comment_id,
        author=author,
        text=optional_string(raw, "content"),
        published_at=timestamp(raw, "timestamp"),
        observed_at=context.observed_at,
        metrics=CanonicalMetricsV1(like_count=like_count),
        source=source(context, item_locator),
    )


def _kuaishou_parent_comment_id(
    raw: dict[str, Any], root_comment_id: str | None
) -> str | None:
    for key in ("reply_comment_id", "replyCommentId", "parent_comment_id"):
        value = optional_string(raw, key)
        if value not in {None, "0", root_comment_id}:
            return value
    return None


def _content_type(item: dict[str, Any]) -> str:
    duration, duration_present = count(item, "duration")
    if duration_present and duration is not None and duration > 0:
        return "video"
    for key in ("atlas", "cover_urls", "coverUrls"):
        value = item.get(key)
        if isinstance(value, list) and value:
            return "image"
    return "unknown"


def _map_content_author(
    raw: dict[str, Any],
) -> tuple[CanonicalAuthorV1 | None, tuple[str, ...]]:
    external_id = optional_string(raw, "user_id")
    display_name = optional_string(raw, "user_name")
    verified = optional_bool(raw, "verified")
    fields: list[str] = []
    if external_id is not None:
        fields.append("external_account_id")
    if display_name is not None:
        fields.append("display_name")
    if verified is not None:
        fields.append("verified")
    if not fields:
        return None, ()
    return (
        CanonicalAuthorV1(
            external_account_id=external_id,
            display_name=display_name,
            verified=verified,
        ),
        tuple(fields),
    )


def _map_comment_author(raw: dict[str, Any]) -> CanonicalAuthorV1 | None:
    external_id = optional_string(raw, "user_id", "author_id")
    display_name = optional_string(raw, "author_name")
    verified = optional_bool(raw, "authorVerified")
    if external_id is None and display_name is None and verified is None:
        return None
    return CanonicalAuthorV1(
        external_account_id=external_id,
        display_name=display_name,
        verified=verified,
    )


def _map_metrics(raw: dict[str, Any]) -> tuple[CanonicalMetricsV1, tuple[str, ...]]:
    mappings = {
        "like_count": ("like_count",),
        "comment_count": ("comment_count",),
        "favorite_count": ("collect_count",),
        "share_count": ("share_count",),
        "repost_count": ("forward_count",),
        "view_count": ("view_count",),
        "download_count": ("downloadCount",),
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
            view_count=values["view_count"],
            download_count=values["download_count"],
        ),
        tuple(observed),
    )


__all__ = ["KuaishouMappingContext", "map_comment", "map_content"]
