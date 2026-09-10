from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from aima_ugc.modules.ingestion.historical_chunk import (
    HISTORICAL_CHUNK_SCHEMA_VERSION,
    read_historical_chunk,
)


def _write_chunk(path: Path, *, schema_version: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "schema_version": schema_version,
                    "source_row_ordinal": 1,
                    "outcome": "invalid",
                    "content": None,
                    "error_code": "fixture",
                }
            )
            + "\n"
        )


def test_historical_chunk_reader_accepts_only_current_schema(tmp_path: Path) -> None:
    current = tmp_path / "current.jsonl.gz"
    legacy = tmp_path / "legacy.jsonl.gz"
    _write_chunk(current, schema_version=HISTORICAL_CHUNK_SCHEMA_VERSION)
    _write_chunk(legacy, schema_version="historical-canonical-row.v1")

    assert read_historical_chunk(current)[0]["schema_version"] == (HISTORICAL_CHUNK_SCHEMA_VERSION)
    with pytest.raises(ValueError, match="schema_version 不受支持"):
        read_historical_chunk(legacy)
