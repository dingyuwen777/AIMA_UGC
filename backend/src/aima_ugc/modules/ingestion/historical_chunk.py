"""历史 XLSX 到版本化有界 gzip JSONL Chunk 的流式转换。"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

HISTORICAL_CHUNK_SCHEMA_VERSION = "historical-canonical-row.v1"


def read_historical_chunk(
    path: Path,
    *,
    max_rows: int = 2_000,
) -> tuple[dict[str, object], ...]:
    """仅供单个有界 Chunk Worker 读取；调用方仍必须校验 chunk_rows 上限。"""

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
    return tuple(records)


__all__ = [
    "HISTORICAL_CHUNK_SCHEMA_VERSION",
    "read_historical_chunk",
]
