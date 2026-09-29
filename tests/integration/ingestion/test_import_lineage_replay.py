from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.artifact_metadata import (
    PostgresArtifactMetadataRepository,
)
from aima_ugc.adapters.persistence.postgres.import_lineage import (
    ensure_campaign_import_lineage,
    ensure_single_import_lineage,
)
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


def test_excel_lineage_reuses_completed_attempts_for_multi_platform_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """多平台来源可重放，且应用时钟落后数据库时也能完成非计费 Attempt。"""

    monkeypatch.setattr(
        "aima_ugc.adapters.persistence.postgres.import_lineage.beijing_now", lambda: _NOW
    )

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


def test_campaign_lineage_first_use_is_safe_across_replay_shards() -> None:
    """两片同时首次引用同一 Canonical 来源时只形成一个已完成 Attempt。"""

    runtime = DatabaseRuntime(load_settings())
    artifact_id = uuid4()
    batch_id = uuid4()
    setup = runtime.new_session()
    try:
        with setup.begin():
            metadata = PostgresArtifactMetadataRepository(setup)
            metadata.create_pending(
                ArtifactRecord(
                    id=artifact_id,
                    kind="canonical.v1",
                    storage_backend="local",
                    storage_key=f"canonical.v1/{artifact_id}.jsonl",
                    content_type="application/x-ndjson",
                    encoding="utf-8",
                    retention_class="raw",
                    storage_status="pending",
                    created_at=_NOW,
                )
            )
            artifact = metadata.mark_stored(
                artifact_id, sha256="b" * 64, byte_size=128, stored_at=_NOW
            )
            setup.execute(
                insert(processing_import_batches_table).values(
                    id=batch_id,
                    input_artifact_id=artifact_id,
                    status="processing",
                    stats={},
                    created_at=_NOW,
                    started_at=_NOW,
                )
            )

        barrier = Barrier(2)

        def establish() -> tuple[object, object]:
            session = runtime.new_session()
            try:
                barrier.wait(timeout=10)
                with session.begin():
                    return ensure_campaign_import_lineage(
                        session=session,
                        batch_id=batch_id,
                        platform="xiaohongshu",
                        canonical_artifact=artifact,
                        operation="historical_import",
                    )
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: establish(), range(2)))

        assert results[0] == results[1]
        with setup.begin():
            assert (
                setup.scalar(
                    select(func.count())
                    .select_from(provider_request_attempts_table)
                    .where(provider_request_attempts_table.c.id == results[0][1])
                )
                == 1
            )
    finally:
        setup.close()
        runtime.dispose()
