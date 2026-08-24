"""Artifact 字节保留策略。

这里只定义已经由业务确认的时间窗口；业务父事实和 Artifact 元数据不随字节过期删除。
"""

from __future__ import annotations

from datetime import datetime, timedelta

PROVIDER_RAW_RETENTION = timedelta(days=30)
IMPORT_SOURCE_RETENTION = timedelta(days=7)
EXPORT_RETENTION = timedelta(days=7)
ORPHAN_RETENTION = timedelta(days=1)

_INITIAL_RETENTION_BY_KIND = {
    "provider-raw": PROVIDER_RAW_RETENTION,
    "content-export.xlsx": EXPORT_RETENTION,
}


def initial_artifact_expiry(kind: str, created_at: datetime) -> datetime | None:
    """返回创建时即可确定的字节过期时间。

    Excel Import 必须等 Batch 进入终态后再开始 7 天保留期，因此这里故意返回 None。
    """

    if created_at.utcoffset() is None:
        raise ValueError("Artifact created_at 必须包含时区")
    retention = _INITIAL_RETENTION_BY_KIND.get(kind)
    return created_at + retention if retention is not None else None


def import_source_expiry(finished_at: datetime) -> datetime:
    """Excel Import 源文件从 Batch 终态时间开始保留 7 天。"""

    if finished_at.utcoffset() is None:
        raise ValueError("Import finished_at 必须包含时区")
    return finished_at + IMPORT_SOURCE_RETENTION


__all__ = [
    "EXPORT_RETENTION",
    "IMPORT_SOURCE_RETENTION",
    "ORPHAN_RETENTION",
    "PROVIDER_RAW_RETENTION",
    "import_source_expiry",
    "initial_artifact_expiry",
]
