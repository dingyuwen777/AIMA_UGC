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
class XiaohongshuMappingContext:
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
    raw: dict[str, Any], context: XiaohongshuMappingContext, *, item_locator: str
) -> CanonicalContentV1:
    """把搜索卡片或真实详情事实映射为一条原子 Content Observation。"""
    item = _unwrap_content(raw)
    external_id = _required_string(item, "id", "note_id")
    observed_fields: list[str] = ["alternate_ids"]
    content_type = _content_type(item)
    if content_type != "unknown":
        observed_fields.append("content_type")

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

    published_at = _timestamp(item, "create_time", "timestamp", "time", "publish_time")
    if published_at is not None:
        observed_fields.append("published_at")
    source_updated_at = _timestamp(item, "last_update_time", "update_time", "source_updated_at")
    if source_updated_at is not None:
        observed_fields.append("source_updated_at")

    media = _map_media(item)
    complete_media = (
        content_type == "image"
        and isinstance(item.get("images_list"), list)
        and context.operation == "get_image_note_detail"
        and len(media) == len(item["images_list"])
    ) or (
        content_type == "video"
        and context.operation == "get_video_note_detail"
        and bool(_first_dict(item, "video_info_v2", "video_info"))
    )
    if media or complete_media:
        observed_fields.append("media")
    topics = _map_topics(item)
    if topics:
        observed_fields.append("topics")
    locations = _map_locations(item)
    if locations:
        observed_fields.append("locations")

    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=external_id,
        alternate_ids={"note_id": external_id},
        content_type=content_type,
        title=title,
        text=text,
        author=author,
        published_at=published_at,
        source_updated_at=source_updated_at,
        observed_at=context.observed_at,
        media=media,
        media_collection_mode="complete" if complete_media else "partial",
        topics=topics,
        locations=locations,
        metrics=metrics,
        source=_source(context, item_locator),
        observed_fields=observed_fields,
    )


def map_comment(
    raw: dict[str, Any],
    context: XiaohongshuMappingContext,
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
    if parent_comment_id is None:
        parent_comment_id = _optional_string(raw, "target_comment_id", "targetCommentId")
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
        platform="xiaohongshu",
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


def _source(context: XiaohongshuMappingContext, item_locator: str) -> CanonicalSourceV1:
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
        "like_count": ("liked_count", "like_count", "likes"),
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
    """视频的图片列表只是封面；所选流的尺寸与时长不能混用源视频属性。"""
    if _content_type(raw) == "unknown":
        return []
    if _content_type(raw) == "video":
        video_info = _first_dict(raw, "video_info_v2", "video_info")
        media = _first_dict(video_info, "media")
        video = _first_dict(media, "video")
        streams = _first_dict(media, "stream").get("h264")
        stream = (
            next(
                (
                    item
                    for item in streams
                    if isinstance(item, dict)
                    and item.get("video_codec") == "h264"
                    and item.get("format") == "mp4"
                    and item.get("audio_codec") in {None, "aac"}
                ),
                {},
            )
            if isinstance(streams, list)
            else {}
        )
        values: dict[str, Any] = {"media_type": "video"}
        source = stream or video
        for field in ("width", "height"):
            value, _ = _count(source, field)
            if value is not None:
                values[field] = value
        duration, _ = _count(source, "video_duration", "duration")
        if duration is not None:
            values["duration_ms"] = duration if stream else duration * 1000
        video_id = _optional_string(media, "video_id")
        if video_id is not None:
            values["external_media_id"] = video_id
        url = _http_url(stream, "master_url")
        if url is None and isinstance(stream.get("backup_urls"), list):
            url = next(
                (
                    _http_url({"url": item}, "url")
                    for item in stream["backup_urls"]
                    if isinstance(item, str) and item.startswith(("http://", "https://"))
                ),
                None,
            )
        if url is not None:
            values["url"] = url
            values["mime_type"] = "video/mp4"
        image = _first_dict(video_info, "image")
        preview = _http_url(image, "first_frame", "thumbnail")
        images = raw.get("images_list")
        if preview is None and isinstance(images, list):
            preview = next(
                (_http_url(item, "url", "original") for item in images if isinstance(item, dict)),
                None,
            )
        if preview is not None:
            values["preview_url"] = preview
        # 类型已明确即保留视频行；没有播放源仍可以展示封面并受控刷新。
        return [CanonicalMediaV1.model_validate({**values, "observed_fields": list(values)})]

    images = raw.get("images_list")
    if not isinstance(images, list):
        return []
    mapped: list[CanonicalMediaV1] = []
    for fallback_position, image in enumerate(images):
        if not isinstance(image, dict):
            continue
        width, _ = _count(image, "width")
        height, _ = _count(image, "height")
        values = {
            "media_type": "image",
            "external_media_id": _optional_string(image, "fileid", "file_id", "id"),
            "url": _http_url(image, "url", "original", "url_size_large"),
            "width": width,
            "height": height,
        }
        values = {key: value for key, value in values.items() if value is not None}
        if len(values) == 1:
            # 错误占位对象或未知字段不能证明该位置有图片，更不能证明完整全集。
            continue
        # App V2 可能给多张图片重复 index=0，数组顺序才是稳定位置事实。
        mapped.append(
            CanonicalMediaV1.model_validate(
                {
                    **values,
                    "position": fallback_position,
                    "observed_fields": list(values),
                }
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
    """只有 Provider 明确 normal/video 才证明内容类型。"""
    value = (_optional_string(raw, "type", "note_type") or "").lower()
    return {"video": "video", "normal": "image"}.get(value, "unknown")


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
