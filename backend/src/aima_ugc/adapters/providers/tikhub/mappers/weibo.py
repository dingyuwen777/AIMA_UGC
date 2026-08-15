"""TikHub 微博 Search Raw → Canonical 纯 Mapper。"""

from __future__ import annotations

from typing import Any

from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
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
    """把真实 Web Search card.mblog 映射为内容 Observation。"""
    item = first_dict(raw, "mblog")
    if not item:
        raise ValueError("微博 Search card 缺少 mblog")

    external_id = required_string(item, "id", "mid")
    observed_fields: list[str] = ["content_type"]

    alternate_ids: dict[str, str] = {}
    bid = optional_string(item, "bid")
    if bid is not None:
        alternate_ids["bid"] = bid
        observed_fields.append("alternate_ids")

    text = optional_string(item, "text")
    if text is not None:
        observed_fields.append("text")

    author_raw = first_dict(item, "user")
    author, author_fields = _map_author(author_raw)
    observed_fields.extend(f"author.{field}" for field in author_fields)

    metrics, metric_fields = _map_metrics(item)
    observed_fields.extend(f"metrics.{field}" for field in metric_fields)

    published_at = timestamp(item, "created_at")
    if published_at is not None:
        observed_fields.append("published_at")

    return CanonicalContentV1(
        platform="weibo",
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


def _content_type(item: dict[str, Any]) -> str:
    pic_num, present = count(item, "pic_num")
    if present and pic_num is not None and pic_num > 0:
        return "image"
    return "text"


def _map_author(raw: dict[str, Any]) -> tuple[CanonicalAuthorV1 | None, tuple[str, ...]]:
    if not raw:
        return None, ()
    external_id = optional_string(raw, "id", "idstr")
    display_name = optional_string(raw, "screen_name")
    profile_url = http_url(raw, "profile_url")
    bio = optional_string(raw, "description")
    verified = optional_bool(raw, "verified")

    fields: list[str] = []
    if external_id is not None:
        fields.append("external_account_id")
    if display_name is not None:
        fields.append("display_name")
    if profile_url is not None:
        fields.append("profile_url")
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


__all__ = ["WeiboMappingContext", "map_content"]
