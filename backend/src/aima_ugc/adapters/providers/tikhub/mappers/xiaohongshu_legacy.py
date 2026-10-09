"""仅验证 90013af0 以前已冻结 Canonical 的媒体投影，不用于新观察或入库。"""

from typing import Any

from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalMediaV1

from .xiaohongshu import _count, _first_dict, _http_url, _optional_string, _unwrap_content


def legacy_media_projection(current: CanonicalContentV1, raw: dict[str, Any]) -> CanonicalContentV1:
    """其余字段与 Source 必须来自同一次正式 Raw 重放；仅恢复已知旧媒体协议。"""
    item = _unwrap_content(raw)
    content_type = (
        "video"
        if (_optional_string(item, "type", "note_type") or "").lower() == "video"
        else "image"
    )
    media: list[CanonicalMediaV1] = []
    if content_type == "video":
        video = _first_dict(
            _first_dict(_first_dict(item, "video_info_v2", "video_info"), "media"), "video"
        )
        if video:
            duration, _ = _count(video, "duration")
            width, _ = _count(video, "width")
            height, _ = _count(video, "height")
            media = [
                CanonicalMediaV1(
                    media_type="video",
                    width=width,
                    height=height,
                    duration_ms=duration * 1000 if duration is not None else None,
                )
            ]
    if not media and isinstance(item.get("images_list"), list):
        for position, image in enumerate(item["images_list"]):
            if not isinstance(image, dict):
                continue
            width, _ = _count(image, "width")
            height, _ = _count(image, "height")
            media.append(
                CanonicalMediaV1(
                    media_type="image",
                    external_media_id=_optional_string(image, "fileid", "file_id", "id"),
                    url=_http_url(image, "url", "url_size_large"),
                    width=width,
                    height=height,
                    position=position,
                )
            )
    fields = [
        "content_type",
        "alternate_ids",
        *(
            field
            for field in current.observed_fields
            if field not in {"content_type", "alternate_ids", "media", "topics", "locations"}
        ),
    ]
    if media:
        fields.append("media")
    if current.topics:
        fields.append("topics")
    if current.locations:
        fields.append("locations")
    return current.model_copy(
        update={
            "content_type": content_type,
            "media": media,
            "media_collection_mode": "complete",
            "observed_fields": fields,
        }
    )
