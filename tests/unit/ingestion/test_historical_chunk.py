from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from aima_ugc.adapters.providers.imports import historical_chunk
from aima_ugc.adapters.providers.imports.historical_chunk import (
    HistoricalChunkDescriptor,
    convert_historical_excel_to_chunks,
)
from aima_ugc.adapters.providers.imports.models import ExcelImportRow, ExcelImportRowError
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1

_NOW = datetime(2026, 9, 11, tzinfo=UTC)


def _content(row_number: int) -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=f"row-{row_number}",
        content_type="note",
        text="爱玛" if row_number == 2 else "当前过滤不命中的合法内容",
        observed_at=_NOW,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            source_type="aima-monitoring-v1",
            source_value="fixture.xlsx",
            item_locator=f"sheet=文章;row={row_number}",
            observed_at=_NOW,
        ),
        observed_fields=["text"],
    )


def test_historical_converter_publishes_pure_canonical_and_separate_invalid_facts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    rows = tuple(
        ExcelImportRow(row_number=number, sheet_name="文章", values={}) for number in (2, 3, 4)
    )
    monkeypatch.setattr(historical_chunk, "get_excel_import_profile", lambda name: object())
    monkeypatch.setattr(
        historical_chunk,
        "iter_excel_rows",
        lambda path, *, profile: iter(rows),
    )

    def map_row(row, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        if row.row_number == 4:
            raise ExcelImportRowError("fixture_invalid", "fixture")
        return _content(row.row_number)

    monkeypatch.setattr(historical_chunk, "map_excel_row", map_row)
    published: list[tuple[HistoricalChunkDescriptor, bytes]] = []

    def publish(descriptor: HistoricalChunkDescriptor) -> None:
        published.append((descriptor, descriptor.path.read_bytes()))

    summary = convert_historical_excel_to_chunks(
        input_path=tmp_path / "fixture.xlsx",
        output_dir=tmp_path / "chunks",
        profile_name="aima-monitoring-v1",
        observed_at=_NOW,
        chunk_rows=3,
        publish=publish,
    )

    assert summary.rows_seen == 3
    assert summary.canonical_rows == 2
    assert summary.invalid == 1
    assert summary.chunks == 1
    descriptor, payload = published[0]
    assert descriptor.canonical_row_ordinals == (2, 3)
    assert [(item.source_row_ordinal, item.error_code) for item in descriptor.invalid_rows] == [
        (4, "fixture_invalid")
    ]
    records = [json.loads(line) for line in payload.splitlines()]
    assert [record["external_content_id"] for record in records] == ["row-2", "row-3"]
    assert all("outcome" not in record and "content" not in record for record in records)
