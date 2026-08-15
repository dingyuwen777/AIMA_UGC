"""TikHub 微博 Raw → Canonical 纯 Mapper。"""

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
    http_url,
    optional_bool,
    optional_string,
    required_string,
    source,
    timestamp,
)

WeiboMappingContext = TikHubMappingContext


def map_content(
    raw: dict[str, Any], context: WeiboMappingContext, *, item_locator: str
) -> CanonicalContentV1:
    """把真实 Web Search mblog 或 App Detail status 映射为内容 Observation。"""
    item = first_dict(raw, "mblog")
    if not item and "id" in raw and "user" in raw:
        item = raw
    if not item:
        raise ValueError("微博内容缺少 mblog/status")

    external_id = required_string(item, "idstr", "id", "mid")
    observed_fields: list[str] = ["content_type"]

    alternate_ids: dict[str, str] = {}
    for key in ("mid", "bid"):
        value = optional_string(item, key)
        if value is not None and value != external_id:
            alternate_ids[key] = value
    if alternate_ids:
        observed_fields.append("alternate_ids")

    text = optional_string(item, "text", "text_raw")
    if text is not None:
        observed_fields.append("text")

    author, author_fields = _map_author(first_dict(item, "user"))
    observed_fields.extend(f"author.{field}" for field in author_fields)

    metrics, metric_fields = _map_metrics(item)
    observed_fields.extend(f"metrics.{field}" for field in metric_fields)

    published_at = timestamp(item, "created_at")
    if published_at is not None:
        observed_fields.append("published_at")
    source_updated_at = timestamp(item, "edit_at")
    if source_updated_at is not None:
        observed_fields.append("source_updated_at")

    return CanonicalContentV1(
        platform="weibo",
        external_content_id=external_id,
        alternate_ids=alternate_ids,
        content_type=_content_type(item),
        text=text,
        author=author,
        published_at=published_at,
        source_updated_at=source_updated_at,
        observed_at=context.observed_at,
        metrics=metrics,
        source=source(context, item_locator),
        observed_fields=observed_fields,
    )


def map_comment(
    raw: dict[str, Any],
    context: WeiboMappingContext,
    *,
    item_locator: str,
    is_root: bool,
) -> CanonicalCommentV1:
    """把真实 App comment item 映射为统一评论树节点。"""
    external_content_id = context.external_content_id
    if external_content_id is None:
        raise ValueError("微博评论必须由请求上下文提供 external_content_id")
    external_comment_id = required_string(raw, "idstr", "mid", "id")

    observed_fields: list[str] = []
    text = optional_string(raw, "text")
    if text is not None:
        observed_fields.append("text")

    author, author_fields = _map_author(first_dict(raw, "user"))
    observed_fields.extend(f"author.{field}" for field in author_fields)

    like_count, like_observed = count(raw, "like_counts")
    reply_count, reply_observed = count(raw, "total_number")
    if like_observed:
        observed_fields.append("metrics.like_count")
    if reply_observed:
        observed_fields.append("metrics.reply_count")

    published_at = timestamp(raw, "created_at")
    if published_at is not None:
        observed_fields.append("published_at")

    if is_root:
        root_comment_id = external_comment_id
        parent_comment_id = None
        observed_fields.extend(("root_comment_id", "parent_comment_id"))
    else:
        root_comment_id = context.root_comment_id or optional_string(raw, "rootidstr", "rootid")
        parent_comment_id = _weibo_parent_comment_id(raw, root_comment_id)
        if root_comment_id is not None:
            observed_fields.append("root_comment_id")
        if parent_comment_id is not None:
            observed_fields.append("parent_comment_id")

    return CanonicalCommentV1(
        platform="weibo",
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


def _weibo_parent_comment_id(raw: dict[str, Any], root_comment_id: str | None) -> str | None:
    for key in ("reply_id", "replyid", "rid"):
        value = optional_string(raw, key)
        if value not in {None, "0", root_comment_id}:
            return value
    return None


def _content_type(item: dict[str, Any]) -> str:
    pic_num, present = count(item, "pic_num")
    if present and pic_num is not None and pic_num > 0:
        return "image"
    return "text"


def _map_author(raw: dict[str, Any]) -> tuple[CanonicalAuthorV1 | None, tuple[str, ...]]:
    if not raw:
        return None, ()
    external_id = optional_string(raw, "idstr", "id")
    display_name = optional_string(raw, "screen_name")
    profile_url = http_url(raw, "profile_url")
    avatar_url = http_url(raw, "avatar_hd", "avatar_large")
    bio = optional_string(raw, "description")
    verified = optional_bool(raw, "verified")

    fields: list[str] = []
    if external_id is not None:
        fields.append("external_account_id")
    if display_name is not None:
        fields.append("display_name")
    if profile_url is not None:
        fields.append("profile_url")
    if avatar_url is not None:
        fields.append("avatar_url")
    if bio is not None:
        fields.append("bio")
    if verified is not None:
        fields.append("verified")
    if not fields:
        return None, ()

    return (
        CanonicalAuthorV1(
            external_account_id=external_id,
            display_name=display_name,
            profile_url=profile_url,
            avatar_url=avatar_url,
            bio=bio,
            verified=verified,
        ),
        tuple(fields),
    )


def _map_metrics(item: dict[str, Any]) -> tuple[CanonicalMetricsV1, tuple[str, ...]]:
    mappings = {
        "like_count": ("attitudes_count",),
        "comment_count": ("comments_count",),
        "repost_count": ("reposts_count",),
        "favorite_count": ("favorites_count",),
    }
    values: dict[str, int | None] = {}
    observed: list[str] = []
    for canonical, keys in mappings.items():
        value, present = count(item, *keys)
        values[canonical] = value
        if present:
            observed.append(canonical)
    return (
        CanonicalMetricsV1(
            like_count=values["like_count"],
            comment_count=values["comment_count"],
            repost_count=values["repost_count"],
            favorite_count=values["favorite_count"],
        ),
        tuple(observed),
    )


__all__ = ["WeiboMappingContext", "map_comment", "map_content"]
