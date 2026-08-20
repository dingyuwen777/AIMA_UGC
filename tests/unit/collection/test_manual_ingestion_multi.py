from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.bootstrap import manual_ingestion
from aima_ugc.bootstrap.manual_ingestion import FileImportDatabaseSummary
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1


def _record(*, source_value: str, content_id: str) -> UnifiedContentRecordV1:
    observed_at = datetime(2026, 8, 20, tzinfo=UTC)
    return UnifiedContentRecordV1(
        content=CanonicalContentV1(
            platform="weibo",
            external_content_id=content_id,
            content_type="unknown",
            title="爱玛",
            text="正文",
            observed_at=observed_at,
            source=CanonicalSourceV1(
                provider_name="imports",
                operation="excel_import",
                source_type="aima-monitoring-excel.v1",
                source_value=source_value,
                item_locator="sheet=文章;row=2",
                observed_at=observed_at,
            ),
            observed_fields=["title", "text"],
        ),
        matched_keywords=["爱玛"],
    )


def test_multi_file_database_ingestion_creates_one_filtered_batch_per_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    unified = tmp_path / "contents.jsonl"
    unified.write_text(
        _record(source_value="first.xlsx", content_id="one").model_dump_json() + "\n",
        encoding="utf-8",
    )
    runtime = SimpleNamespace(database=object(), close=lambda: None)
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(manual_ingestion, "create_platform_runtime", lambda _: runtime)

    def fake_ingest(**kwargs):
        calls.append(kwargs)
        return FileImportDatabaseSummary(
            batch_id=uuid4(),
            input_artifact_id=uuid4(),
            rows_seen=kwargs["rows_seen"],
            rows_ingested=1 if kwargs["source_value_filter"] == "first.xlsx" else 0,
            rows_rejected=0,
            provider_request_count=1 if kwargs["source_value_filter"] == "first.xlsx" else 0,
        )

    monkeypatch.setattr(manual_ingestion, "_ingest_excel_run", fake_ingest)

    summary = manual_ingestion.ingest_excel_files_run_to_postgres(
        source_rows=((first, 3), (second, 4)),
        unified_content_path=unified,
    )

    assert [call["input_path"] for call in calls] == [first, second]
    assert [call["source_value_filter"] for call in calls] == [
        "first.xlsx",
        "second.xlsx",
    ]
    assert all(call["unified_content_path"] == unified for call in calls)
    assert summary.rows_seen == 7
    assert summary.rows_ingested == 1
    assert summary.rows_rejected == 0
    assert summary.provider_request_count == 1


def test_multi_file_database_ingestion_rejects_unknown_source_before_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.xlsx"
    first.write_bytes(b"first")
    unified = tmp_path / "contents.jsonl"
    unified.write_text(
        _record(source_value="other.xlsx", content_id="one").model_dump_json() + "\n",
        encoding="utf-8",
    )
    runtime_called = False

    def runtime_must_not_start(_: str):
        nonlocal runtime_called
        runtime_called = True
        raise AssertionError("来源预检失败前不得连接数据库")

    monkeypatch.setattr(manual_ingestion, "create_platform_runtime", runtime_must_not_start)

    with pytest.raises(ValueError, match="不属于本次 Excel 输入"):
        manual_ingestion.ingest_excel_files_run_to_postgres(
            source_rows=((first, 1),),
            unified_content_path=unified,
        )

    assert runtime_called is False
