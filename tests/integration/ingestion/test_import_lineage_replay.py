from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.import_lineage import ensure_single_import_lineage
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.storage import ArtifactRecord
from sqlalchemy import func, insert, select

_NOW = datetime(2026, 9, 11, 2, 0, tzinfo=UTC)


def test_excel_lineage_reuses_completed_attempts_for_multi_platform_batch() -> None:
    """同一文件的多平台逻辑 Request 可合并，但每个平台 Attempt 必须可重放复用。"""

    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    transaction = session.begin()
    try:
        artifact_id = uuid4()
        artifact_repository = PostgresArtifactMetadataRepository(session)
        artifact_repository.create_pending(
            ArtifactRecord(
                id=artifact_id,
                kind="file-import.raw",
                storage_backend="local",
                storage_key=f"file-import.raw/{artifact_id}.xlsx",
                content_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                encoding=None,
                retention_class="raw",
                storage_status="pending",
                created_at=_NOW,
            )
        )
        artifact = artifact_repository.mark_stored(
            artifact_id,
            sha256="a" * 64,
            byte_size=128,
            stored_at=_NOW,
        )
        batch_id = uuid4()
        session.execute(
            insert(processing_import_batches_table).values(
                id=batch_id,
                input_artifact_id=artifact.id,
                status="processing",
                stats={},
                created_at=_NOW,
                started_at=_NOW,
            )
        )

        first = ensure_single_import_lineage(
            session=session,
            batch_id=batch_id,
            platform="xiaohongshu",
            input_artifact=artifact,
            profile="aima-monitoring-excel.v1",
        )
        second = ensure_single_import_lineage(
            session=session,
            batch_id=batch_id,
            platform="douyin",
            input_artifact=artifact,
            profile="aima-monitoring-excel.v1",
        )

        assert (
            ensure_single_import_lineage(
                session=session,
                batch_id=batch_id,
                platform="xiaohongshu",
                input_artifact=artifact,
                profile="aima-monitoring-excel.v1",
            )
            == first
        )
        assert (
            ensure_single_import_lineage(
                session=session,
                batch_id=batch_id,
                platform="douyin",
                input_artifact=artifact,
                profile="aima-monitoring-excel.v1",
            )
            == second
        )
        assert first[0] == second[0]
        assert first[1] != second[1]
        assert (
            session.scalar(
                select(func.count())
                .select_from(provider_requests_table)
                .where(provider_requests_table.c.import_batch_id == batch_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(provider_request_attempts_table)
                .where(provider_request_attempts_table.c.provider_request_id == first[0])
            )
            == 2
        )
    finally:
        transaction.rollback()
        session.close()
        runtime.dispose()
