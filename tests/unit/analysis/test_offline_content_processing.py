from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.analysis.offline_content import (
    ContentDeduplicationConflictError,
    deduplicate_content_jsonl,
    filter_canonical_content_jsonl,
)

OBSERVED_AT = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


def _content(
    *,
    external_content_id: str,
    title: str,
    text: str,
    item_locator: str,
    platform: str = "xiaohongshu",
) -> CanonicalContentV1:
    return CanonicalContentV1(
        observed_fields=["title", "text"],
        platform=platform,
        external_content_id=external_content_id,
        content_type="unknown",
        title=title,
        text=text,
        observed_at=OBSERVED_AT,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            source_type="aima-monitoring-excel.v1",
            source_value="source.xlsx",
            item_locator=item_locator,
            observed_at=OBSERVED_AT,
        ),
    )


def _write_jsonl(path: Path, records: list[CanonicalContentV1 | UnifiedContentRecordV1]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{record.model_dump_json()}\n" for record in records),
        encoding="utf-8",
    )


def test_filter_keywords_matches_title_and_text_and_writes_unified_records(tmp_path: Path) -> None:
    source = tmp_path / "canonical" / "contents.jsonl"
    output = tmp_path / "filtered" / "contents.jsonl"
    _write_jsonl(
        source,
        [
            _content(
                external_content_id="content-1",
                title="爱玛新品发布",
                text="电动车体验升级",
                item_locator="sheet=文章;row=2",
            ),
            _content(
                external_content_id="content-2",
                title="行业观察",
                text="正文中提到爱玛",
                item_locator="sheet=文章;row=3",
            ),
            _content(
                external_content_id="content-3",
                title="行业观察",
                text="其他品牌内容",
                item_locator="sheet=文章;row=4",
            ),
        ],
    )

    summary = filter_canonical_content_jsonl(
        input_path=source,
        output_path=output,
        keywords=("爱玛", "电动车"),
    )

    assert summary.rows_seen == 3
    assert summary.rows_written == 2
    assert summary.rows_filtered_out == 1
    records = [
        UnifiedContentRecordV1.model_validate_json(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert [record.content.external_content_id for record in records] == ["content-1", "content-2"]
    assert records[0].matched_keywords == ["爱玛", "电动车"]
    assert records[1].matched_keywords == ["爱玛"]
    assert all(record.analysis is None for record in records)


def test_filter_keywords_cleans_keyword_config_and_preserves_first_seen_order(
    tmp_path: Path,
) -> None:
    source = tmp_path / "canonical" / "contents.jsonl"
    output = tmp_path / "filtered" / "contents.jsonl"
    _write_jsonl(
        source,
        [
            _content(
                external_content_id="content-1",
                title="爱玛新品发布",
                text="电动车体验升级",
                item_locator="sheet=文章;row=2",
            )
        ],
    )

    filter_canonical_content_jsonl(
        input_path=source,
        output_path=output,
        keywords=(" 爱玛 ", "爱玛", "电动车", " 电动车 "),
    )

    record = UnifiedContentRecordV1.model_validate_json(output.read_text(encoding="utf-8").strip())
    assert record.matched_keywords == ["爱玛", "电动车"]


def test_deduplicate_collapses_equivalent_identity_and_keeps_first_locator(tmp_path: Path) -> None:
    source = tmp_path / "filtered" / "contents.jsonl"
    output = tmp_path / "deduplicated" / "contents.jsonl"
    first = UnifiedContentRecordV1(
        content=_content(
            external_content_id="content-1",
            title="爱玛新品发布",
            text="正文",
            item_locator="sheet=文章;row=2",
        ),
        matched_keywords=["爱玛"],
    )
    duplicate = UnifiedContentRecordV1(
        content=_content(
            external_content_id="content-1",
            title="爱玛新品发布",
            text="正文",
            item_locator="sheet=文章;row=8",
        ),
        matched_keywords=["爱玛"],
    )
    _write_jsonl(source, [first, duplicate])

    summary = deduplicate_content_jsonl(input_path=source, output_path=output)

    assert summary.rows_seen == 2
    assert summary.rows_written == 1
    assert summary.duplicates_removed == 1
    assert summary.conflicts == 0
    record = UnifiedContentRecordV1.model_validate_json(output.read_text(encoding="utf-8").strip())
    assert record.content.source.item_locator == "sheet=文章;row=2"


def test_deduplicate_conflict_fails_closed_without_publishing_partial_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "filtered" / "contents.jsonl"
    output = tmp_path / "deduplicated" / "contents.jsonl"
    first = UnifiedContentRecordV1(
        content=_content(
            external_content_id="content-1",
            title="爱玛新品发布",
            text="正文",
            item_locator="sheet=文章;row=2",
        ),
        matched_keywords=["爱玛"],
    )
    conflict = UnifiedContentRecordV1(
        content=_content(
            external_content_id="content-1",
            title="同一身份但标题发生变化",
            text="正文",
            item_locator="sheet=文章;row=9",
        ),
        matched_keywords=["爱玛"],
    )
    another = UnifiedContentRecordV1(
        content=_content(
            external_content_id="content-2",
            title="爱玛另一条内容",
            text="正文",
            item_locator="sheet=文章;row=10",
        ),
        matched_keywords=["爱玛"],
    )
    _write_jsonl(source, [first, conflict, another])

    with pytest.raises(ContentDeduplicationConflictError) as exc_info:
        deduplicate_content_jsonl(input_path=source, output_path=output)

    summary = exc_info.value.summary
    assert summary.rows_seen == 3
    assert summary.rows_written == 2
    assert summary.duplicates_removed == 0
    assert summary.conflicts == 1
    assert not output.exists()
    conflicts = [
        json.loads(line)
        for line in summary.conflict_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert conflicts == [
        {
            "platform": "xiaohongshu",
            "external_content_id": "content-1",
            "first_line": 1,
            "duplicate_line": 2,
            "different_fields": ["content.title"],
        }
    ]
    assert "爱玛新品发布" not in summary.conflict_path.read_text(encoding="utf-8")
    assert "同一身份但标题发生变化" not in summary.conflict_path.read_text(encoding="utf-8")
