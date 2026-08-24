from datetime import UTC, datetime
from uuid import uuid4

from aima_ugc.bootstrap.reporting_http import _export_expired
from aima_ugc.modules.reporting.models import DataExportRecord


def _export(completed_at: datetime) -> DataExportRecord:
    return DataExportRecord(
        id=uuid4(),
        job_id=uuid4(),
        artifact_id=uuid4(),
        request_snapshot={},
        stats={},
        created_at=completed_at,
        completed_at=completed_at,
    )


def test_export_download_fails_closed_after_retention_window() -> None:
    completed_at = datetime(2000, 1, 1, tzinfo=UTC)

    assert _export_expired(
        _export(completed_at),
        expires_at=None,
        stored_at=completed_at,
        created_at=completed_at,
    ) is True


def test_export_download_remains_available_before_retention_deadline() -> None:
    completed_at = datetime(2099, 1, 1, tzinfo=UTC)

    assert _export_expired(
        _export(completed_at),
        expires_at=None,
        stored_at=completed_at,
        created_at=completed_at,
    ) is False
