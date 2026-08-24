from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aima_ugc.bootstrap.manual_ingestion import ingest_excel_run_to_postgres
from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.content.extended_tables import content_external_ids_table
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import func, select

_STABLE_ID = "excel-stable-content"


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    with runtime.engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE TABLE jobs, artifacts, accounts RESTART IDENTITY CASCADE"
        )
    try:
        yield runtime
    finally:
        with runtime.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, accounts RESTART IDENTITY CASCADE"
            )
        runtime.dispose()


def _content(*, alternate_ids: dict[str, str], observed_at: datetime) -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=_STABLE_ID,
        alternate_ids=alternate_ids,
        content_type="note",
        title="爱玛身份合并回归",
        observed_at=observed_at,
        source=CanonicalSourceV1(
            provider_name="imports",
            operation="excel_import",
            source_type="file",
            source_value="identity.xlsx",
            item_locator=f"identity:{observed_at.isoformat()}",
            observed_at=observed_at,
        ),
        observed_fields=["content_type", "title", "alternate_ids"],
    )


def _write_run(
    tmp_path: Path,
    *,
    name: str,
    content: CanonicalContentV1,
) -> tuple[Path, Path]:
    xlsx = tmp_path / f"{name}.xlsx"
    xlsx.write_bytes(f"xlsx:{name}".encode())
    jsonl = tmp_path / f"{name}.jsonl"
    jsonl.write_text(
        UnifiedContentRecordV1(
            content=content,
            matched_keywords=["爱玛"],
        ).model_dump_json()
        + "\n",
        encoding="utf-8",
    )
    return xlsx, jsonl


def test_external_ids_merge_by_type_and_keep_newer_value(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    newer_at = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    older_missing_type_at = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
    older_conflict_at = datetime(2026, 8, 24, 11, 0, tzinfo=UTC)

    runs = (
        (
            "new-native",
            _content(alternate_ids={"note_id": "provider-note-new"}, observed_at=newer_at),
        ),
        (
            "older-share",
            _content(
                alternate_ids={"share_text": "https://xhslink.com/example"},
                observed_at=older_missing_type_at,
            ),
        ),
        (
            "older-conflict",
            _content(alternate_ids={"note_id": "provider-note-old"}, observed_at=older_conflict_at),
        ),
    )
    for name, content in runs:
        xlsx, jsonl = _write_run(tmp_path, name=name, content=content)
        summary = ingest_excel_run_to_postgres(
            input_path=xlsx,
            unified_content_path=jsonl,
            rows_seen=1,
        )
        assert summary.rows_ingested == 1

    with database_runtime.engine.connect() as connection:
        content_id = connection.scalar(
            select(contents_table.c.id).where(
                contents_table.c.platform == "xiaohongshu",
                contents_table.c.external_content_id == _STABLE_ID,
            )
        )
        assert content_id is not None
        rows = connection.execute(
            select(
                content_external_ids_table.c.id_type,
                content_external_ids_table.c.external_id,
            )
            .where(content_external_ids_table.c.content_id == content_id)
            .order_by(content_external_ids_table.c.id_type)
        ).all()
        content_count = connection.scalar(
            select(func.count()).select_from(contents_table).where(
                contents_table.c.platform == "xiaohongshu",
                contents_table.c.external_content_id == _STABLE_ID,
            )
        )

    assert dict(rows) == {
        "note_id": "provider-note-new",
        "share_text": "https://xhslink.com/example",
    }
    assert content_count == 1
