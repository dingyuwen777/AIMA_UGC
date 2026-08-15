"""TikHub 小红书 App V2 Raw → Canonical 纯 Mapper。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import AnyHttpUrl

from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalCommentV1,
    CanonicalContentV1,
    CanonicalLocationV1,
    CanonicalMediaV1,
    CanonicalMetricsV1,
    CanonicalSourceV1,
    CanonicalTopicV1,
)


@dataclass(frozen=True, slots=True)
class XhsMappingContext:
    """Mapper 显式采集上下文；不包含 Secret。"""

    provider_request_id: str
    provider_attempt_id: str
    raw_artifact_id: UUID
    operation: str
    source_type: str
    source_value: str
    observed_at: datetime
    root_comment_id: str | None = None


def map_content(
    raw: dict[str, Any], context: XhsMappingContext, *, item_locator: str
) -> CanonicalContentV1:
    """把搜索卡片或真实详情事实映射为一条原子 Content Observation。"""
    item = _unwrap_content(raw)
    external_id = _required_string(item, "id", "note_id")
    observed_fields: list[str] = ["content_type"]

    title = _optional_string(item, "title")
    text = _optional_string(item, "desc", "text", "content")
    if title is not None:
        observed_fields.append("title")
    if text is not None:
        observed_fields.append("text")

    author_raw = _first_dict(item, "user", "user_info", "author")
    author, author_fields = _map_author(author_raw)
    observed_fields.extend(f"author.{field}" for field in author_fields)

    metrics, metric_fields = _map_content_metrics(item)
    observed_fields.extend(f"metrics.{field}" for field in metric_fields)

    published_at = _timestamp(item, "timestamp", "time", "publish_time")
    if published_at is not None:
        observed_fields.append("published_at")
    source_updated_at = _timestamp(item, "last_update_time", "update_time", "source_updated_at")
    if source_updated_at is not None:
        observed_fields.append("source_updated_at")

    media = _map_media(item)
    if media:
        observed_fields.append("media")
    topics = _map_topics(item)
    if topics:
        observed_fields.append("topics")
    locations = _map_locations(item)
    if locations:
        observed_fields.append("locations")

    return CanonicalContentV1(
        platform="xhs",
        external_content_id=external_id,
        content_type=_content_type(item),
        title=title,
        text=text,
        author=author,
        published_at=published_at,
        source_updated_at=source_updated_at,
        observed_at=context.observed_at,
        media=media,
        topics=topics,
        locations=locations,
        metrics=metrics,
        source=_source(context, item_locator),
        observed_fields=observed_fields,
    )


def map_comment(
    raw: dict[str, Any],
    context: XhsMappingContext,
    *,
    item_locator: str,
    is_root: bool,
) -> CanonicalCommentV1:
    """把一级评论或回复映射为 Comment Observation，不猜测直接父评论。"""
    external_comment_id = _required_string(raw, "id", "comment_id")
    external_content_id = _required_string(raw, "note_id", "noteId")
    observed_fields: list[str] = []

    text = _optional_string(raw, "content", "text")
    if text is not None:
        observed_fields.append("text")

    author_raw = _first_dict(raw, "user_info", "user", "author")
    author, author_fields = _map_author(author_raw)
    observed_fields.extend(f"author.{field}" for field in author_fields)

    like_count, like_observed = _count(raw, "like_count", "liked_count")
    reply_count, reply_observed = _count(raw, "sub_comment_count", "reply_count")
    metrics = CanonicalMetricsV1(like_count=like_count, reply_count=reply_count)
    if like_observed:
        observed_fields.append("metrics.like_count")
    if reply_observed:
        observed_fields.append("metrics.reply_count")

    published_at = _timestamp(raw, "create_time", "timestamp", "time")
    if published_at is not None:
        observed_fields.append("published_at")
    source_updated_at = _timestamp(raw, "update_time", "source_updated_at")
    if source_updated_at is not None:
        observed_fields.append("source_updated_at")

    explicit_parent = _first_dict(raw, "target_comment", "targetComment")
    parent_comment_id: str | None = _optional_string(explicit_parent, "id", "comment_id")
    root_comment_id: str | None
    if is_root:
        root_comment_id = external_comment_id
        parent_comment_id = None
        observed_fields.extend(("root_comment_id", "parent_comment_id"))
    else:
        root_comment_id = context.root_comment_id or _optional_string(
            raw, "root_comment_id", "root_commentId"
        )
        if root_comment_id is not None:
            observed_fields.append("root_comment_id")
        if parent_comment_id is not None:
            observed_fields.append("parent_comment_id")

    return CanonicalCommentV1(
        platform="xhs",
        external_content_id=external_content_id,
        external_comment_id=external_comment_id,
        root_comment_id=root_comment_id,
        parent_comment_id=parent_comment_id,
        author=author,
        text=text,
        published_at=published_at,
        source_updated_at=source_updated_at,
        observed_at=context.observed_at,
        metrics=metrics,
        source=_source(context, item_locator),
        observed_fields=observed_fields,
    )


def _source(context: XhsMappingContext, item_locator: str) -> CanonicalSourceV1:
    return CanonicalSourceV1(
        provider_name="tikhub",
        operation=context.operation,
        provider_request_id=context.provider_request_id,
        provider_attempt_id=context.provider_attempt_id,
        raw_artifact_id=context.raw_artifact_id,
        source_type=context.source_type,
        source_value=context.source_value,
        item_locator=item_locator,
        observed_at=context.observed_at,
    )


def _unwrap_content(raw: dict[str, Any]) -> dict[str, Any]:
    for key in ("note", "note_card", "noteCard"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return raw


def _map_author(
    raw: dict[str, Any],
) -> tuple[CanonicalAuthorV1 | None, tuple[str, ...]]:
    if not raw:
        return None, ()
    external_id = _optional_string(raw, "userid", "user_id", "userId", "id")
    red_id = _optional_string(raw, "red_id", "redId")
    display_name = _optional_string(raw, "nickname", "nick_name", "name")
    verified = _optional_bool(raw, "red_official_verified", "verified")

    fields: list[str] = []
    alternate_ids: dict[str, str] = {}
    if external_id is not None:
        fields.append("external_account_id")
    if red_id is not None:
        alternate_ids["red_id"] = red_id
        fields.append("alternate_ids")
    if display_name is not None:
        fields.append("display_name")
    if verified is not None:
        fields.append("verified")
    if not fields:
        return None, ()

    return (
        CanonicalAuthorV1(
            external_account_id=external_id,
            alternate_ids=alternate_ids,
            display_name=display_name,
            verified=verified,
        ),
        tuple(fields),
    )


def _map_content_metrics(
    raw: dict[str, Any],
) -> tuple[CanonicalMetricsV1, tuple[str, ...]]:
    mapping = {
        "like_count": ("liked_count", "like_count"),
        "comment_count": ("comments_count", "comment_count"),
        "favorite_count": ("collected_count", "collect_count", "favorite_count"),
        "share_count": ("shared_count", "share_count"),
        "view_count": ("view_count",),
    }
    values: dict[str, int | None] = {}
    observed: list[str] = []
    interact = _first_dict(raw, "interact_info", "interactInfo")
    for canonical, keys in mapping.items():
        value, present = _count(raw, *keys)
        if not present and interact:
            value, present = _count(interact, *keys)
        values[canonical] = value
        if present:
            observed.append(canonical)
    return (
        CanonicalMetricsV1(
            like_count=values.get("like_count"),
            comment_count=values.get("comment_count"),
            favorite_count=values.get("favorite_count"),
            share_count=values.get("share_count"),
            view_count=values.get("view_count"),
        ),
        tuple(observed),
    )


def _map_media(raw: dict[str, Any]) -> list[CanonicalMediaV1]:
    if _content_type(raw) == "video":
        video_info = _first_dict(raw, "video_info_v2", "video_info")
        media = _first_dict(video_info, "media")
        video = _first_dict(media, "video")
        if video:
            duration, _ = _count(video, "duration")
            width, _ = _count(video, "width")
            height, _ = _count(video, "height")
            return [
                CanonicalMediaV1(
                    media_type="video",
                    width=width,
                    height=height,
                    duration_ms=duration * 1000 if duration is not None else None,
                )
            ]

    images = raw.get("images_list")
    if not isinstance(images, list):
        return []
    mapped: list[CanonicalMediaV1] = []
    for fallback_position, image in enumerate(images):
        if not isinstance(image, dict):
            continue
        width, _ = _count(image, "width")
        height, _ = _count(image, "height")
        position, position_present = _count(image, "index")
        mapped.append(
            CanonicalMediaV1(
                media_type="image",
                external_media_id=_optional_string(image, "fileid", "file_id", "id"),
                url=_http_url(image, "url", "url_size_large"),
                width=width,
                height=height,
                position=position
                if position_present and position is not None
                else fallback_position,
            )
        )
    return mapped


def _map_topics(raw: dict[str, Any]) -> list[CanonicalTopicV1]:
    topics = raw.get("topics")
    if not isinstance(topics, list):
        return []
    mapped: list[CanonicalTopicV1] = []
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        name = _optional_string(topic, "name", "topic_name")
        if name is None:
            continue
        mapped.append(
            CanonicalTopicV1(
                name=name,
                external_topic_id=_optional_string(topic, "id", "topic_id"),
                url=_http_url(topic, "link", "url"),
            )
        )
    return mapped


def _map_locations(raw: dict[str, Any]) -> list[CanonicalLocationV1]:
    ip_location = _optional_string(raw, "ip_location")
    if ip_location is not None:
        return [CanonicalLocationV1(location_type="ip_region", label=ip_location)]
    geo = _first_dict(raw, "geo_info", "geoInfo")
    label = _optional_string(geo, "poi_name", "name", "address")
    if label is not None:
        return [CanonicalLocationV1(location_type="place", label=label)]
    return []


def _content_type(raw: dict[str, Any]) -> str:
    value = (_optional_string(raw, "type", "note_type") or "").lower()
    return "video" if value == "video" else "image"


def _timestamp(raw: dict[str, Any], *keys: str) -> datetime | None:
    for key in keys:
        if key not in raw or raw[key] is None:
            continue
        value = raw[key]
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            seconds = float(value)
            if seconds > 10_000_000_000:
                seconds /= 1000
            try:
                return datetime.fromtimestamp(seconds, tz=UTC)
            except OverflowError, OSError, ValueError:
                return None
    return None


def _count(raw: dict[str, Any], *keys: str) -> tuple[int | None, bool]:
    for key in keys:
        if key not in raw:
            continue
        value = raw[key]
        if value is None:
            return None, True
        if isinstance(value, bool):
            return None, False
        try:
            parsed = int(value)
        except TypeError, ValueError:
            return None, False
        return (parsed if parsed >= 0 else None), parsed >= 0
    return None, False


def _http_url(raw: dict[str, Any], *keys: str) -> AnyHttpUrl | None:
    value = _optional_string(raw, *keys)
    if value is None or not value.startswith(("http://", "https://")):
        return None
    try:
        return AnyHttpUrl(value)
    except ValueError:
        return None


def _optional_bool(raw: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, bool):
            return value
    return None


def _required_string(raw: dict[str, Any], *keys: str) -> str:
    value = _optional_string(raw, *keys)
    if value is None:
        raise ValueError(f"缺少稳定外部 ID: {keys}")
    return value


def _optional_string(raw: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in raw and raw[key] is not None:
            value = str(raw[key]).strip()
            if value:
                return value
    return None


def _first_dict(raw: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return {}
