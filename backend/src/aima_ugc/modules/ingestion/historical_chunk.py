"""历史 XLSX 到版本化有界 gzip JSONL Chunk 的读取边界。"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

HISTORICAL_CHUNK_SCHEMA_VERSION = "historical-canonical-row.v2"


def read_historical_chunk(
    path: Path,
    *,
    max_rows: int = 2_000,
) -> tuple[dict[str, object], ...]:
    """读取单个当前版本有界 Chunk；Worker 还会校验 Campaign Snapshot。"""

    if max_rows < 1 or max_rows > 2_000:
        raise ValueError("Historical Chunk max_rows 必须在 1 到 2000 之间")
    records: list[dict[str, object]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("Historical Chunk 行必须是 JSON object")
            if payload.get("schema_version") != HISTORICAL_CHUNK_SCHEMA_VERSION:
                raise ValueError("Historical Chunk schema_version 不受支持")
            records.append(payload)
            if len(records) > max_rows:
                raise ValueError("Historical Chunk 行数超过冻结上限")
    versions = {record.get("schema_version") for record in records}
    if len(versions) > 1:
        raise ValueError("同一 Historical Chunk 不能混合多个 schema_version")
    return tuple(records)


__all__ = [
    "HISTORICAL_CHUNK_SCHEMA_VERSION",
    "read_historical_chunk",
]
