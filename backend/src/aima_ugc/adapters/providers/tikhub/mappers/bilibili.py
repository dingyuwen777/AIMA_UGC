"""TikHub B站 Search Raw → Canonical 纯 Mapper。"""

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
    optional_string,
    required_string,
    source,
    timestamp,
)

BilibiliMappingContext = TikHubMappingContext


def map_content(
    raw: dict[str, Any], context: BilibiliMappingContext, *, item_locator: str
) -> CanonicalContentV1:
    """把真实 App 分类搜索 av item 映射为视频 Observation。"""
    av = first_dict(raw, "av")
    if not av:
        raise ValueError("B站 Search item 缺少 av")

    external_id = required_string(raw, "param")
    observed_fields: list[str] = ["content_type"]

    title = optional_string(av, "title")
    text = optional_string(av, "view_content", "show_card_desc_2")
    if title is not None:
        observed_fields.append("title")
    if text is not None:
        observed_fields.append("text")

    canonical_url = http_url(raw, "uri")
    if canonical_url is not None:
        observed_fields.append("canonical_url")

    author, author_fields = _map_author(av)
    observed_fields.extend(f"author.{field}" for field in author_fields)

    metrics, metric_fields = _map_metrics(av)
    observed_fields.extend(f"metrics.{field}" for field in metric_fields)

    published_at = timestamp(av, "ptime")
    if published_at is not None:
        observed_fields.append("published_at")

    return CanonicalContentV1(
        platform="bilibili",
        external_content_id=external_id,
        content_type="video",
        title=title,
        text=text,
        canonical_url=canonical_url,
        author=author,
        published_at=published_at,
        observed_at=context.observed_at,
        metrics=metrics,
        source=source(context, item_locator),
        observed_fields=observed_fields,
    )


def _map_author(raw: dict[str, Any]) -> tuple[CanonicalAuthorV1 | None, tuple[str, ...]]:
    external_id = optional_string(raw, "mid")
    display_name = optional_string(raw, "author")
    avatar_url = http_url(raw, "face")
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


def _map_metrics(raw: dict[str, Any]) -> tuple[CanonicalMetricsV1, tuple[str, ...]]:
    play_count, play_present = count(raw, "play")
    danmaku_count, danmaku_present = count(raw, "danmaku")
    observed: list[str] = []
    if play_present:
        observed.append("play_count")
    if danmaku_present:
        observed.append("danmaku_count")
    return (
        CanonicalMetricsV1(play_count=play_count, danmaku_count=danmaku_count),
        tuple(observed),
    )


__all__ = ["BilibiliMappingContext", "map_content"]
