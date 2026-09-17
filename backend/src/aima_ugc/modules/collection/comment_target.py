"""评论 Provider 参数与 Canonical 内容身份之间的显式解析边界。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from aima_ugc.contracts.platform import PlatformName

ResolutionState = Literal["resolved", "unavailable"]

_LOOKUP_ID_PRIORITY: dict[PlatformName, tuple[str, ...]] = {
    "xiaohongshu": ("note_id",),
    "douyin": ("aweme_id",),
    "weibo": ("status_id",),
    "bilibili": ("av_id", "bv_id"),
    "kuaishou": ("photo_id",),
}
_LOCATION_ID_TYPES: dict[PlatformName, tuple[str, ...]] = {
    "xiaohongshu": ("share_text",),
    "douyin": ("douyin_share_url",),
    "weibo": ("weibo_video_url",),
    "bilibili": ("bilibili_share_url",),
    "kuaishou": ("kuaishou_share_url",),
}
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_BV_ID = re.compile(r"^BV[A-Za-z0-9]{10}$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CommentTargetResolution:
    """保留 Canonical 主身份，并独立说明评论目标是否已获证明。"""

    state: ResolutionState
    canonical_external_content_id: str
    platform: PlatformName
    lookup_id_type: str | None = None
    lookup_id: str | None = None
    source: str | None = None
    failure_code: str | None = None


def resolve_comment_target(
    *,
    platform: PlatformName,
    external_content_id: str,
    alternate_ids: dict[str, str] | None,
    source: str = "imported_typed_id",
) -> CommentTargetResolution:
    """仅从该平台允许的 typed ID 解析评论参数，不推断主身份的来源。"""

    ids = alternate_ids or {}
    # 历史数据可能已带有该定位字段；长文章不进入当前 TikHub 帖子评论接口。
    if platform == "weibo" and "ttarticle_id" in ids:
        return CommentTargetResolution(
            state="unavailable",
            canonical_external_content_id=external_content_id,
            platform=platform,
            failure_code="identity_unavailable",
        )
    # BV/av 前缀本身就是 B站原生身份；旧 Canonical 行没有 typed 别名时仍可确定性识别。
    if platform == "bilibili" and not ids:
        if _BV_ID.fullmatch(external_content_id):
            ids = {"bv_id": external_content_id}
            source = "canonical_permalink"
        elif (
            external_content_id[:2].casefold() == "av"
            and external_content_id[2:].isascii()
            and external_content_id[2:].isdecimal()
        ):
            ids = {"av_id": external_content_id}
            source = "canonical_permalink"
    for id_type in _LOOKUP_ID_PRIORITY[platform]:
        value = ids.get(id_type, "").strip()
        if _valid_lookup_id(id_type, value):
            if id_type == "av_id" and value[:2].casefold() == "av":
                value = value[2:]
            return CommentTargetResolution(
                state="resolved",
                canonical_external_content_id=external_content_id,
                platform=platform,
                lookup_id_type=id_type,
                lookup_id=value,
                source=source,
            )
    return CommentTargetResolution(
        state="unavailable",
        canonical_external_content_id=external_content_id,
        platform=platform,
        failure_code="identity_unavailable",
    )


def _valid_lookup_id(id_type: str, value: str) -> bool:
    """阻止 URL、来源哈希和跨平台类型进入 TikHub 评论参数。"""

    if not value:
        return False
    if id_type in {"aweme_id", "status_id"}:
        return value.isascii() and value.isdecimal()
    if id_type == "av_id":
        candidate = value[2:] if value[:2].casefold() == "av" else value
        return candidate.isascii() and candidate.isdecimal()
    if id_type == "bv_id":
        return _BV_ID.fullmatch(value) is not None
    return _OPAQUE_ID.fullmatch(value) is not None


def identity_block_reason(platform: PlatformName, alternate_ids: dict[str, str]) -> str:
    """有定位身份但缺少精确映射时，与完全缺失身份使用不同原因。"""

    if platform == "weibo" and "ttarticle_id" in alternate_ids:
        return "identity_unavailable"
    return (
        "exact_resolution_unavailable"
        if any(alternate_ids.get(id_type) for id_type in _LOCATION_ID_TYPES[platform])
        else "identity_unavailable"
    )
