"""TikHub B站 Raw → Canonical 纯 Mapper。"""

from __future__ import annotations

from typing import Any

from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
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

BilibiliMappingContext = TikHubMappingContext


def map_content(
    raw: dict[str, Any], context: BilibiliMappingContext, *, item_locator: str
) -> CanonicalContentV1:
    """把真实 App Search item 或 Detail data 映射为视频 Observation。"""
    search_av = first_dict(raw, "av")
    is_search = bool(search_av)
    item = search_av if is_search else raw
    if is_search:
        external_id = required_string(raw, "param")
        alternate_ids: dict[str, str] = {}
    else:
        external_id = required_string(item, "aid")
        alternate_ids = {}
        bvid = optional_string(item, "bvid")
        if bvid is not None:
            alternate_ids["bvid"] = bvid

    observed_fields: list[str] = ["content_type"]
    if alternate_ids:
        observed_fields.append("alternate_ids")

    title = optional_string(item, "title")
    text = optional_string(item, "desc", "view_content", "show_card_desc_2")
    if title is not None:
        observed_fields.append("title")
    if text is not None:
        observed_fields.append("text")

    canonical_url = http_url(raw, "uri") if is_search else None
    if canonical_url is not None:
        observed_fields.append("canonical_url")

    author, author_fields = _map_author(item, is_search=is_search)
    observed_fields.extend(f"author.{field}" for field in author_fields)

    metrics, metric_fields = _map_metrics(item, is_search=is_search)
    observed_fields.extend(f"metrics.{field}" for field in metric_fields)

    published_at = timestamp(item, "pubdate", "ptime")
    if published_at is not None:
        observed_fields.append("published_at")

    media = _map_media(item, is_search=is_search)
    if media:
        observed_fields.append("media")

    return CanonicalContentV1(
        platform="bilibili",
        external_content_id=external_id,
        alternate_ids=alternate_ids,
        content_type="video",
        title=title,
        text=text,
        canonical_url=canonical_url,
        author=author,
        published_at=published_at,
        observed_at=context.observed_at,
        media=media,
        metrics=metrics,
        source=source(context, item_locator),
        observed_fields=observed_fields,
    )


def _map_author(
    raw: dict[str, Any], *, is_search: bool
) -> tuple[CanonicalAuthorV1 | None, tuple[str, ...]]:
    author_raw = raw if is_search else first_dict(raw, "owner")
    external_id = optional_string(author_raw, "mid")
    display_name = optional_string(author_raw, "author", "name")
    avatar_url = http_url(author_raw, "face")
    fields: list[str] = []
    if external_id is not None:
        fields.append("external_account_id")
    if display_name is not None:
        fields.append("display_name")
    if avatar_url is not None:
        fields.append("avatar_url")
    if not fields:
        return None, ()
    return (
        CanonicalAuthorV1(
            external_account_id=external_id,
            display_name=display_name,
            avatar_url=avatar_url,
        ),
        tuple(fields),
    )


def _map_metrics(
    raw: dict[str, Any], *, is_search: bool
) -> tuple[CanonicalMetricsV1, tuple[str, ...]]:
    metrics_raw = raw if is_search else first_dict(raw, "stat")
    mappings = {
        "like_count": ("like",),
        "comment_count": ("reply",),
        "share_count": ("share",),
        "favorite_count": ("favorite",),
        "view_count": ("view", "play"),
        "play_count": ("play", "view"),
        "danmaku_count": ("danmaku",),
        "coin_count": ("coin",),
    }
    values: dict[str, int | None] = {}
    observed: list[str] = []
    for canonical, keys in mappings.items():
        value, present = count(metrics_raw, *keys)
        values[canonical] = value
        if present:
            observed.append(canonical)
    return (
        CanonicalMetricsV1(
            like_count=values["like_count"],
            comment_count=values["comment_count"],
            share_count=values["share_count"],
            favorite_count=values["favorite_count"],
            view_count=values["view_count"],
            play_count=values["play_count"],
            danmaku_count=values["danmaku_count"],
            coin_count=values["coin_count"],
        ),
        tuple(observed),
    )


def _map_media(raw: dict[str, Any], *, is_search: bool) -> list[CanonicalMediaV1]:
    if is_search:
        cover_url = http_url(raw, "cover")
        return [CanonicalMediaV1(media_type="cover", url=cover_url)] if cover_url else []
    cover_url = http_url(raw, "pic")
    duration, _ = count(raw, "duration")
    if cover_url is None and duration is None:
        return []
    return [
        CanonicalMediaV1(
            media_type="cover",
            url=cover_url,
            duration_ms=duration * 1000 if duration is not None else None,
        )
    ]


__all__ = ["BilibiliMappingContext", "map_content"]
