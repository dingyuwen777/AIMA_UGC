"""Analysis Target 集合指纹的 PostgreSQL 聚合辅助。"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import BigInteger, func, literal


def target_snapshot_columns(
    content_id_column: Any,
    content_version_column: Any,
) -> tuple[Any, Any, Any]:
    """返回 count + 双 64-bit 哈希和；聚合不搬运全量 Target 到 Python。"""

    token = func.concat(content_id_column, literal(":"), content_version_column)
    seed0 = literal(0, type_=BigInteger())
    seed1 = literal(1, type_=BigInteger())
    return (
        func.count().label("target_count"),
        func.coalesce(func.sum(func.hashtextextended(token, seed0)), 0).label("target_hash_sum0"),
        func.coalesce(func.sum(func.hashtextextended(token, seed1)), 0).label("target_hash_sum1"),
    )


def target_snapshot_fingerprint(
    *,
    target_count: int,
    hash_sum0: int,
    hash_sum1: int,
) -> str:
    """把数据库聚合值收敛为稳定 SHA-256 文本，供 Run 内部快照比较。"""

    payload = f"{target_count}:{hash_sum0}:{hash_sum1}".encode("ascii")
    return hashlib.sha256(payload).hexdigest()


__all__ = ["target_snapshot_columns", "target_snapshot_fingerprint"]
