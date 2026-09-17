"""Artifact 字节保留与媒体缓存容量策略。

这里只定义已经由业务确认的时间窗口和缓存水位；业务父事实和 Artifact 元数据
不随字节过期删除。
"""

from __future__ import annotations

from datetime import datetime, timedelta

PROVIDER_RAW_RETENTION = timedelta(days=30)
IMPORT_SOURCE_RETENTION = timedelta(days=7)
EXPORT_RETENTION = timedelta(days=7)
FEISHU_PUBLICATION_INPUT_RETENTION = timedelta(days=7)
ORPHAN_RETENTION = timedelta(days=1)
MEDIA_CACHE_RETENTION = timedelta(days=30)
MEDIA_CACHE_ITEM_MAX_BYTES = 10 * 1024 * 1024
MEDIA_CACHE_MAX_BYTES = 30 * 1024 * 1024 * 1024
MEDIA_CACHE_TARGET_BYTES = 24 * 1024 * 1024 * 1024

_INITIAL_RETENTION_BY_KIND = {
    "provider-raw": PROVIDER_RAW_RETENTION,
    "content-media-cache": MEDIA_CACHE_RETENTION,
    "feishu-publication.input": FEISHU_PUBLICATION_INPUT_RETENTION,
}


def initial_artifact_expiry(kind: str, created_at: datetime) -> datetime | None:
    """返回创建时即可确定的字节过期时间。

    Provider Raw 与 Content Media Cache 创建时即可开始 30 天保留期。Excel Import
    必须等任务终态，Excel Export 必须等 Export 完成，因此两者在业务父事实终态后
    再补 expires_at。
    """

    if created_at.utcoffset() is None:
        raise ValueError("Artifact created_at 必须包含时区")
    retention = _INITIAL_RETENTION_BY_KIND.get(kind)
    return created_at + retention if retention is not None else None


def import_source_expiry(finished_at: datetime) -> datetime:
    """Excel Import 源文件从任务终态时间开始保留 7 天。"""

    if finished_at.utcoffset() is None:
        raise ValueError("Import finished_at 必须包含时区")
    return finished_at + IMPORT_SOURCE_RETENTION


__all__ = [
    "EXPORT_RETENTION",
    "FEISHU_PUBLICATION_INPUT_RETENTION",
    "IMPORT_SOURCE_RETENTION",
    "MEDIA_CACHE_ITEM_MAX_BYTES",
    "MEDIA_CACHE_MAX_BYTES",
    "MEDIA_CACHE_RETENTION",
    "MEDIA_CACHE_TARGET_BYTES",
    "ORPHAN_RETENTION",
    "PROVIDER_RAW_RETENTION",
    "import_source_expiry",
    "initial_artifact_expiry",
]
